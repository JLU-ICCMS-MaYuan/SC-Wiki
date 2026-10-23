package handlers

import (
	"bytes"
	"encoding/json"
	"errors"
	"net/http/httptest"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/alicebob/miniredis/v2"
	"github.com/gin-gonic/gin"
	"golang.org/x/crypto/bcrypt"
	"gorm.io/driver/sqlite"
	"gorm.io/gorm"
	"scwiki/server/cache"
	"scwiki/server/database"
	"scwiki/server/middleware"
	"scwiki/server/models"
)

func (mailer *verificationFakeMailer) SendPasswordChangeCode(email, code string) error {
	return mailer.SendVerificationCode(email, code)
}

func passwordFixture(t *testing.T) (*gin.Engine, *verificationFakeMailer, *miniredis.Miniredis, models.User, string) {
	t.Helper()
	db, err := gorm.Open(sqlite.Open(":memory:"), &gorm.Config{})
	if err != nil {
		t.Fatal(err)
	}
	sqlDB, _ := db.DB()
	sqlDB.SetMaxOpenConns(1)
	t.Cleanup(func() { sqlDB.Close() })
	if err = db.AutoMigrate(&models.User{}); err != nil {
		t.Fatal(err)
	}
	database.DB = db
	redis := miniredis.RunT(t)
	cache.Connect(redis.Addr())
	mailer := &verificationFakeMailer{}
	authMailer = mailer
	verificationSecret = []byte("password-test-secret")
	middleware.InitJWT("password-test-secret")
	hash, _ := bcrypt.GenerateFromPassword([]byte("OldPassword123!"), bcrypt.MinCost)
	user := models.User{Email: "owner@example.test", Username: "Owner", PasswordHash: string(hash), Role: "admin", AccountStatus: "active", IsApproved: true, IsEmailVerified: true}
	if err = db.Create(&user).Error; err != nil {
		t.Fatal(err)
	}
	token, _ := middleware.GenerateTokenForUser(user)
	router := gin.New()
	router.Use(middleware.AuthRequired)
	router.POST("/send", SendPasswordChangeCode)
	router.POST("/change", ChangePassword)
	router.GET("/profile", GetAccountProfile)
	return router, mailer, redis, user, token
}

func passwordRequest(t *testing.T, router *gin.Engine, token, path string, body any) *httptest.ResponseRecorder {
	t.Helper()
	data, _ := json.Marshal(body)
	request := httptest.NewRequest("POST", path, bytes.NewReader(data))
	request.Header.Set("Content-Type", "application/json")
	if token != "" {
		request.Header.Set("Authorization", "Bearer "+token)
	}
	response := httptest.NewRecorder()
	router.ServeHTTP(response, request)
	return response
}

func TestPasswordChangeIdentityAndMandatoryCode(t *testing.T) {
	r, m, _, _, token := passwordFixture(t)
	for _, body := range []map[string]string{{"current_password": "wrong", "email": "owner@example.test"}, {"current_password": "OldPassword123!", "email": "other@example.test"}, {"current_password": "OldPassword123!"}} {
		got := passwordRequest(t, r, token, "/send", body)
		if got.Code < 400 || m.code != "" {
			t.Fatalf("identity bypass: %d %s", got.Code, got.Body)
		}
	}
	if got := passwordRequest(t, r, token, "/change", map[string]string{"current_password": "OldPassword123!", "new_password": "NewPassword123!"}); got.Code != 400 {
		t.Fatal(got.Code, got.Body)
	}
	if got := passwordRequest(t, r, "", "/send", map[string]string{}); got.Code != 401 {
		t.Fatal(got.Code)
	}
}

func TestPasswordChangeConsumeAndRevokeSessions(t *testing.T) {
	r, m, _, user, token := passwordFixture(t)
	send := map[string]string{"current_password": "OldPassword123!", "email": "OWNER@example.test"}
	got := passwordRequest(t, r, token, "/send", send)
	if got.Code != 202 {
		t.Fatal(got.Code, got.Body)
	}
	if m.email != user.Email || len(m.code) != 6 || strings.Contains(got.Body.String(), m.code) {
		t.Fatal("wrong delivery or code leak")
	}
	if got = passwordRequest(t, r, token, "/send", send); got.Code != 429 {
		t.Fatal("no cooldown", got.Code)
	}
	body := map[string]string{"current_password": "OldPassword123!", "email": user.Email, "code": m.code, "new_password": "NewPassword123!"}
	if got = passwordRequest(t, r, token, "/change", body); got.Code != 204 {
		t.Fatal(got.Code, got.Body)
	}
	if got = passwordRequest(t, r, token, "/change", body); got.Code != 401 {
		t.Fatal("old session survived", got.Code)
	}
	database.DB.First(&user, user.ID)
	if user.SessionVersion != 1 || bcrypt.CompareHashAndPassword([]byte(user.PasswordHash), []byte(body["new_password"])) != nil {
		t.Fatal("password/session not updated")
	}
	newToken, _ := middleware.GenerateTokenForUser(user)
	body["current_password"] = "NewPassword123!"
	body["new_password"] = "AnotherPassword123!"
	if got = passwordRequest(t, r, newToken, "/change", body); got.Code != 400 {
		t.Fatal("code reused across session", got.Code)
	}
}

func TestPasswordChangeCodeExpiryAttemptsAndPurpose(t *testing.T) {
	for _, scenario := range []string{"expired", "attempts", "registration", "other-user"} {
		t.Run(scenario, func(t *testing.T) {
			r, m, redis, user, token := passwordFixture(t)
			if got := passwordRequest(t, r, token, "/send", map[string]string{"current_password": "OldPassword123!", "email": user.Email}); got.Code != 202 {
				t.Fatal(got.Code)
			}
			body := map[string]string{"current_password": "OldPassword123!", "email": user.Email, "code": m.code, "new_password": "NewPassword123!"}
			switch scenario {
			case "expired":
				redis.FastForward(6 * time.Minute)
			case "attempts":
				wrong := "000000"
				if wrong == m.code {
					wrong = "111111"
				}
				body["code"] = wrong
				for i := 0; i < 5; i++ {
					got := passwordRequest(t, r, token, "/change", body)
					expected := 400
					if i == 4 {
						expected = 429
					}
					if got.Code != expected {
						t.Fatal(i, got.Code, got.Body)
					}
				}
				body["code"] = m.code
			case "registration":
				cache.Delete("verify:code:" + passwordCodeScope(user))
				cache.PublishVerificationCode(emailKey(user.Email), verificationDigest(user.Email, m.code), verificationTTL)
			case "other-user":
				other := user
				other.ID = 0
				other.Username = "Other"
				other.Email = "other@example.test"
				database.DB.Create(&other)
				token, _ = middleware.GenerateTokenForUser(other)
				body["email"] = other.Email
			}
			if got := passwordRequest(t, r, token, "/change", body); got.Code != 400 {
				t.Fatal("invalid code accepted", got.Code, got.Body)
			}
		})
	}
}

func TestPasswordChangeSendFailuresAndResend(t *testing.T) {
	t.Run("smtp", func(t *testing.T) {
		r, m, _, user, token := passwordFixture(t)
		m.err = errors.New("smtp refused")
		got := passwordRequest(t, r, token, "/send", map[string]string{"current_password": "OldPassword123!", "email": user.Email})
		if got.Code != 503 {
			t.Fatal(got.Code)
		}
		got = passwordRequest(t, r, token, "/change", map[string]string{"current_password": "OldPassword123!", "email": user.Email, "code": m.code, "new_password": "NewPassword123!"})
		if got.Code != 400 {
			t.Fatal("failed delivery produced valid code", got.Code)
		}
	})
	t.Run("redis", func(t *testing.T) {
		r, m, redis, user, token := passwordFixture(t)
		redis.Close()
		got := passwordRequest(t, r, token, "/send", map[string]string{"current_password": "OldPassword123!", "email": user.Email})
		if got.Code != 503 || m.code != "" {
			t.Fatal(got.Code)
		}
	})
	t.Run("resend", func(t *testing.T) {
		r, m, redis, user, token := passwordFixture(t)
		body := map[string]string{"current_password": "OldPassword123!", "email": user.Email}
		passwordRequest(t, r, token, "/send", body)
		redis.FastForward(61 * time.Second)
		if got := passwordRequest(t, r, token, "/send", body); got.Code != 202 {
			t.Fatal(got.Code, got.Body)
		}
		body["code"] = m.code
		body["new_password"] = "NewPassword123!"
		if got := passwordRequest(t, r, token, "/change", body); got.Code != 204 {
			t.Fatal(got.Code, got.Body)
		}
	})
}

func TestPasswordChangeConcurrentConsumption(t *testing.T) {
	r, mailer, _, user, token := passwordFixture(t)
	body := map[string]string{"current_password": "OldPassword123!", "email": user.Email}
	if got := passwordRequest(t, r, token, "/send", body); got.Code != 202 {
		t.Fatal(got.Code)
	}
	body["code"], body["new_password"] = mailer.code, "ConcurrentPassword123!"
	var wg sync.WaitGroup
	statuses := make(chan int, 2)
	for i := 0; i < 2; i++ {
		wg.Add(1)
		go func() { defer wg.Done(); statuses <- passwordRequest(t, r, token, "/change", body).Code }()
	}
	wg.Wait()
	close(statuses)
	successes := 0
	for status := range statuses {
		if status == 204 {
			successes++
		}
	}
	if successes != 1 {
		t.Fatalf("concurrent successes = %d", successes)
	}
	database.DB.First(&user, user.ID)
	if user.SessionVersion != 1 {
		t.Fatal("session changed more than once")
	}
}

func TestPasswordChangeRejectsRevokedInFlightSession(t *testing.T) {
	_, _, _, user, _ := passwordFixture(t)
	scope := passwordCodeScope(user)
	cache.PublishVerificationCode(scope, verificationDigest(scope, "123456"), verificationTTL)
	database.DB.Model(&user).Update("session_version", 1)
	user.SessionVersion = 0
	router := gin.New()
	router.POST("/change", func(c *gin.Context) { c.Set("current_user", &user); ChangePassword(c) })
	got := passwordRequest(t, router, "", "/change", map[string]string{"current_password": "OldPassword123!", "email": user.Email, "code": "123456", "new_password": "NewPassword123!"})
	if got.Code != 403 {
		t.Fatal("stale authenticated request accepted", got.Code, got.Body)
	}
}

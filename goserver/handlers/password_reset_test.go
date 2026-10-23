package handlers

import (
	"encoding/json"
	"errors"
	"fmt"
	"net/http/httptest"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/alicebob/miniredis/v2"
	"github.com/gin-gonic/gin"
	"gorm.io/gorm"
	"scwiki/server/cache"
	"scwiki/server/database"
	"scwiki/server/middleware"
	"scwiki/server/models"
)

func resetFixture(t *testing.T) (*gin.Engine, *verificationFakeMailer, *miniredis.Miniredis, models.User, string) {
	_, mailer, redis, user, token := passwordFixture(t)
	r := gin.New()
	r.POST("/request", RequestPasswordReset)
	r.POST("/verify", VerifyPasswordReset)
	r.POST("/complete", CompletePasswordReset)
	r.POST("/login", loginHandler)
	r.POST("/register-verify", VerifyEmail)
	r.GET("/me", middleware.AuthRequired, GetCurrentUser)
	return r, mailer, redis, user, token
}

func resetPost(t *testing.T, r *gin.Engine, path string, body any, want int) map[string]any {
	t.Helper()
	response := jsonRequest(t, r, "POST", path, body)
	if response.Code != want {
		t.Fatalf("%s: got %d want %d: %s", path, response.Code, want, response.Body)
	}
	result := map[string]any{}
	if want != 204 {
		if err := json.Unmarshal(response.Body.Bytes(), &result); err != nil {
			t.Fatal(err)
		}
	}
	return result
}

func resetGrant(t *testing.T, r *gin.Engine, m *verificationFakeMailer, email string) string {
	t.Helper()
	resetPost(t, r, "/request", gin.H{"email": email}, 202)
	if len(m.code) != 6 {
		t.Fatal("missing delivered code")
	}
	result := resetPost(t, r, "/verify", gin.H{"email": email, "code": m.code}, 200)
	return result["reset_token"].(string)
}

func TestPasswordResetFullFlowAndSessionRevocation(t *testing.T) {
	r, m, redis, user, oldToken := resetFixture(t)
	grant := resetGrant(t, r, m, strings.ToUpper(user.Email))
	if len(grant) != 64 {
		t.Fatal("weak reset token")
	}
	for _, key := range redis.Keys() {
		value, _ := redis.Get(key)
		if value == grant || value == m.code {
			t.Fatal("plaintext credential stored")
		}
	}
	body := gin.H{"email": user.Email, "reset_token": grant, "new_password": "NewPassword123!"}
	resetPost(t, r, "/complete", body, 204)
	resetPost(t, r, "/complete", body, 400)
	resetPost(t, r, "/login", gin.H{"email": user.Email, "password": "OldPassword123!"}, 401)
	resetPost(t, r, "/login", gin.H{"email": user.Email, "password": "NewPassword123!"}, 200)
	req := httptest.NewRequest("GET", "/me", nil)
	req.Header.Set("Authorization", "Bearer "+oldToken)
	response := httptest.NewRecorder()
	r.ServeHTTP(response, req)
	if response.Code != 401 {
		t.Fatal("old session still valid", response.Code)
	}
	var updated models.User
	database.DB.First(&updated, user.ID)
	if updated.SessionVersion != user.SessionVersion+1 || updated.Role != user.Role || !updated.IsEmailVerified {
		t.Fatal("invalid account mutation")
	}
}

func TestPasswordResetUnknownInactiveAndUnverified(t *testing.T) {
	for _, state := range []string{"unknown", "banned", "deactivated", "unverified"} {
		t.Run(state, func(t *testing.T) {
			r, m, _, user, _ := resetFixture(t)
			email := user.Email
			if state == "unknown" {
				email = "nobody@example.test"
			} else if state == "unverified" {
				database.DB.Model(&user).Update("is_email_verified", false)
			} else {
				database.DB.Model(&user).Update("account_status", state)
			}
			result := resetPost(t, r, "/request", gin.H{"email": email}, 202)
			if m.code != "" || result["message"] != "如果该邮箱已注册且可用，将收到验证码" {
				t.Fatal("account enumeration or unexpected mail")
			}
			resetPost(t, r, "/verify", gin.H{"email": email, "code": "123456"}, 400)
			resetPost(t, r, "/complete", gin.H{"email": email, "reset_token": strings.Repeat("a", 64), "new_password": "NewPassword123!"}, 400)
		})
	}
}

func TestPasswordResetIsolationExpiryAndReplacement(t *testing.T) {
	r, m, redis, user, _ := resetFixture(t)
	resetPost(t, r, "/request", gin.H{"email": user.Email}, 202)
	code := m.code
	resetPost(t, r, "/request", gin.H{"email": user.Email}, 429)
	// 注册码和已登录改密码均不能兑换匿名重置授权。
	cache.PublishVerificationCode(emailKey(user.Email), verificationDigest(user.Email, "012345"), verificationTTL)
	cache.PublishVerificationCode(passwordCodeScope(user), verificationDigest(passwordCodeScope(user), "012345"), verificationTTL)
	if code == "012345" {
		t.Skip("random code collision")
	}
	resetPost(t, r, "/verify", gin.H{"email": user.Email, "code": "012345"}, 400)
	redis.FastForward(verificationTTL + time.Second)
	resetPost(t, r, "/verify", gin.H{"email": user.Email, "code": code}, 400)
	grant := resetGrant(t, r, m, user.Email)
	resetPost(t, r, "/verify", gin.H{"email": user.Email, "code": m.code}, 400)
	redis.FastForward(61 * time.Second)
	resetPost(t, r, "/request", gin.H{"email": user.Email}, 202)
	resetPost(t, r, "/complete", gin.H{"email": user.Email, "reset_token": grant, "new_password": "NewPassword123!"}, 400)
	result := resetPost(t, r, "/verify", gin.H{"email": user.Email, "code": m.code}, 200)
	redis.FastForward(verificationTTL + time.Second)
	resetPost(t, r, "/complete", gin.H{"email": user.Email, "reset_token": result["reset_token"], "new_password": "NewPassword123!"}, 400)
}

func TestPasswordResetFailedAttemptsAndValidation(t *testing.T) {
	r, m, _, user, _ := resetFixture(t)
	resetPost(t, r, "/request", gin.H{"email": "bad-email"}, 400)
	resetPost(t, r, "/request", gin.H{"email": user.Email}, 202)
	wrong := "000000"
	if m.code == wrong {
		wrong = "000001"
	}
	for i := 0; i < 5; i++ {
		want := 400
		if i == 4 {
			want = 429
		}
		resetPost(t, r, "/verify", gin.H{"email": user.Email, "code": wrong}, want)
	}
	resetPost(t, r, "/verify", gin.H{"email": user.Email, "code": m.code}, 400)
	for _, password := range []string{"short", strings.Repeat("x", 73), strings.Repeat("密", 25)} {
		resetPost(t, r, "/complete", gin.H{"email": user.Email, "reset_token": strings.Repeat("a", 64), "new_password": password}, 400)
	}
}

func TestPasswordResetConcurrentSingleConsumption(t *testing.T) {
	r, m, _, user, _ := resetFixture(t)
	grant := resetGrant(t, r, m, user.Email)
	statuses := make(chan int, 8)
	var wg sync.WaitGroup
	for i := 0; i < 8; i++ {
		wg.Add(1)
		go func(i int) {
			defer wg.Done()
			response := jsonRequest(t, r, "POST", "/complete", gin.H{"email": user.Email, "reset_token": grant, "new_password": fmt.Sprintf("NewPassword%d!", i)})
			statuses <- response.Code
		}(i)
	}
	wg.Wait()
	close(statuses)
	success := 0
	for status := range statuses {
		if status == 204 {
			success++
		} else if status != 400 {
			t.Fatal("unexpected status", status)
		}
	}
	if success != 1 {
		t.Fatal("reset consumed more than once", success)
	}
}

func TestPasswordResetRevokedIdentityAndFailures(t *testing.T) {
	for _, change := range []string{"session", "email", "banned", "unverified", "database"} {
		t.Run(change, func(t *testing.T) {
			r, m, _, user, _ := resetFixture(t)
			grant := resetGrant(t, r, m, user.Email)
			want := 400
			switch change {
			case "session":
				database.DB.Model(&user).Update("session_version", user.SessionVersion+1)
			case "email":
				database.DB.Model(&user).Update("email", "new@example.test")
			case "banned":
				database.DB.Model(&user).Update("account_status", "banned")
			case "unverified":
				database.DB.Model(&user).Update("is_email_verified", false)
			case "database":
				database.DB.Callback().Update().Before("gorm:update").Register("fail_reset", func(tx *gorm.DB) { tx.AddError(errors.New("injected db failure")) })
				want = 503
			}
			resetPost(t, r, "/complete", gin.H{"email": user.Email, "reset_token": grant, "new_password": "NewPassword123!"}, want)
		})
	}
	t.Run("mail", func(t *testing.T) {
		r, m, redis, user, _ := resetFixture(t)
		m.err = errors.New("mail unavailable")
		resetPost(t, r, "/request", gin.H{"email": user.Email}, 503)
		if redis.Exists("verify:code:" + resetScope(user)) {
			t.Fatal("code published after failed delivery")
		}
	})
	t.Run("cache", func(t *testing.T) {
		r, _, redis, user, _ := resetFixture(t)
		redis.SetError("injected unavailable")
		resetPost(t, r, "/request", gin.H{"email": user.Email}, 503)
		resetPost(t, r, "/verify", gin.H{"email": user.Email, "code": "123456"}, 503)
	})
}

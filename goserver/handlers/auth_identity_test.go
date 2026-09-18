package handlers

import (
	"bytes"
	"encoding/json"
	"errors"
	"net/http"
	"net/http/httptest"
	"testing"

	"scwiki/server/cache"
	"scwiki/server/database"
	"scwiki/server/middleware"
	"scwiki/server/models"

	"github.com/alicebob/miniredis/v2"
	"github.com/gin-gonic/gin"
	"gorm.io/driver/sqlite"
	"gorm.io/gorm"
)

type verificationFakeMailer struct {
	email string
	code  string
	err   error
}

func (mailer *verificationFakeMailer) SendVerificationCode(email, code string) error {
	mailer.email, mailer.code = email, code
	return mailer.err
}

func identityTestRouter(t *testing.T) (*gin.Engine, *verificationFakeMailer) {
	t.Helper()
	db, err := gorm.Open(sqlite.Open(":memory:"), &gorm.Config{})
	if err != nil {
		t.Fatal(err)
	}
	if err := db.AutoMigrate(&models.User{}); err != nil {
		t.Fatal(err)
	}
	database.DB = db
	redisServer := miniredis.RunT(t)
	cache.Connect(redisServer.Addr())
	mailer := &verificationFakeMailer{}
	authMailer = mailer
	verificationSecret = []byte("identity-test-secret")
	middleware.InitJWT("identity-test-secret")
	gin.SetMode(gin.TestMode)
	router := gin.New()
	router.POST("/register", registerHandler)
	router.POST("/login", loginHandler)
	router.POST("/verify", VerifyEmail)
	router.POST("/resend", ResendVerification)
	return router, mailer
}

func jsonRequest(t *testing.T, router *gin.Engine, method, path string, body any) *httptest.ResponseRecorder {
	t.Helper()
	data, err := json.Marshal(body)
	if err != nil {
		t.Fatal(err)
	}
	request := httptest.NewRequest(method, path, bytes.NewReader(data))
	request.Header.Set("Content-Type", "application/json")
	response := httptest.NewRecorder()
	router.ServeHTTP(response, request)
	return response
}

func TestRegisterRequiresEmailVerificationBeforeLogin(t *testing.T) {
	router, mailer := identityTestRouter(t)
	registered := jsonRequest(t, router, http.MethodPost, "/register", map[string]any{
		"email": "Researcher@Example.Test", "password": "strong-pass-123", "username": "Researcher", "real_name": "研究者",
	})
	if registered.Code != http.StatusAccepted {
		t.Fatalf("register = %d %s", registered.Code, registered.Body.String())
	}
	if !bytes.Contains(registered.Body.Bytes(), []byte(`"requires_email_verification":true`)) {
		t.Fatalf("register body = %s", registered.Body.String())
	}
	var user models.User
	if err := database.DB.Where("email = ?", "researcher@example.test").First(&user).Error; err != nil {
		t.Fatal(err)
	}
	if user.Role != "user" || !user.IsApproved || user.IsEmailVerified || user.AccountStatus != "active" {
		t.Fatalf("registered user = %#v", user)
	}
	if mailer.email != user.Email || len(mailer.code) != 6 {
		t.Fatalf("verification email missing: %q %q", mailer.email, mailer.code)
	}
	loggedIn := jsonRequest(t, router, http.MethodPost, "/login", map[string]string{"email": user.Email, "password": "strong-pass-123"})
	if loggedIn.Code != http.StatusForbidden || !bytes.Contains(loggedIn.Body.Bytes(), []byte("email_not_verified")) {
		t.Fatalf("login = %d %s", loggedIn.Code, loggedIn.Body.String())
	}
	verified := jsonRequest(t, router, "POST", "/verify", map[string]string{"email": user.Email, "code": mailer.code})
	if verified.Code != 200 || !bytes.Contains(verified.Body.Bytes(), []byte("access_token")) {
		t.Fatalf("verify: %d %s", verified.Code, verified.Body)
	}
	replay := jsonRequest(t, router, "POST", "/verify", map[string]string{"email": user.Email, "code": mailer.code})
	if replay.Code != 400 {
		t.Fatalf("replay = %d", replay.Code)
	}
	loggedIn = jsonRequest(t, router, "POST", "/login", map[string]string{"email": user.Email, "password": "strong-pass-123"})
	if loggedIn.Code != 200 {
		t.Fatalf("login = %d", loggedIn.Code)
	}
}

func TestRegisterDoesNotReportGenericDatabaseFailureAsDuplicate(t *testing.T) {
	router, _ := identityTestRouter(t)
	if err := database.DB.Callback().Create().Before("gorm:create").Register("test:fail-create", func(tx *gorm.DB) {
		tx.AddError(errors.New("forced create failure"))
	}); err != nil {
		t.Fatal(err)
	}
	response := jsonRequest(t, router, http.MethodPost, "/register", map[string]any{
		"email": "failure@example.test", "password": "strong-pass-123", "username": "FailureUser",
	})
	if response.Code != http.StatusInternalServerError || !bytes.Contains(response.Body.Bytes(), []byte(`"error":"注册失败"`)) {
		t.Fatalf("register = %d %s", response.Code, response.Body.String())
	}
}

func TestVerificationSendRateLimit(t *testing.T) {
	redisServer := miniredis.RunT(t)
	cache.Connect(redisServer.Addr())
	for attempt := 1; attempt <= 5; attempt++ {
		if attempt > 1 {
			cache.Delete("verify:cooldown:" + emailKey("rate@example.test"))
		}
		if retry, err := checkSendLimits("rate@example.test", "192.0.2.1"); err != nil || retry != 0 {
			t.Fatalf("attempt %d = retry %d, error %v", attempt, retry, err)
		}
	}
	cache.Delete("verify:cooldown:" + emailKey("rate@example.test"))
	if retry, err := checkSendLimits("rate@example.test", "192.0.2.1"); err != nil || retry == 0 {
		t.Fatalf("sixth attempt = retry %d, error %v", retry, err)
	}
}

func TestRegistrationMailFailureCanResumeWithoutChangingCredentials(t *testing.T) {
	router, mailer := identityTestRouter(t)
	mailer.err = errors.New("SMTP unavailable")
	response := jsonRequest(t, router, "POST", "/register", map[string]string{"email": "resume@example.test", "username": "ResumeUser", "password": "strong-pass-123", "role": "superadmin"})
	if response.Code != 503 || !bytes.Contains(response.Body.Bytes(), []byte("requires_email_verification")) {
		t.Fatalf("response %d %s", response.Code, response.Body)
	}
	var user models.User
	database.DB.Where("email = ?", "resume@example.test").First(&user)
	if user.IsEmailVerified || user.Role != "user" {
		t.Fatal("unverified user permissions incorrect")
	}
	login := jsonRequest(t, router, "POST", "/login", map[string]string{"email": user.Email, "password": "strong-pass-123"})
	if login.Code != 403 {
		t.Fatalf("login = %d", login.Code)
	}
	mailer.err = nil
	cache.Delete("verify:cooldown:" + emailKey(user.Email))
	resend := jsonRequest(t, router, "POST", "/resend", map[string]string{"email": user.Email, "password": "strong-pass-123"})
	if resend.Code != 202 {
		t.Fatalf("resend = %d %s", resend.Code, resend.Body)
	}
	verified := jsonRequest(t, router, "POST", "/verify", map[string]string{"email": user.Email, "code": mailer.code})
	if verified.Code != 200 {
		t.Fatalf("verify = %d %s", verified.Code, verified.Body)
	}
}

func TestVerificationCooldownWrongAttemptsAndResendReset(t *testing.T) {
	router, mailer := identityTestRouter(t)
	email := "retry@example.test"
	jsonRequest(t, router, "POST", "/register", map[string]string{"email": email, "username": "RetryUser", "password": "strong-pass-123"})
	old := mailer.code
	resend := jsonRequest(t, router, "POST", "/resend", map[string]string{"email": email, "password": "strong-pass-123"})
	if resend.Code != 429 || resend.Header().Get("Retry-After") == "" {
		t.Fatalf("cooldown = %d", resend.Code)
	}
	wrong := "000000"
	if old == wrong {
		wrong = "111111"
	}
	for i := 1; i <= 5; i++ {
		r := jsonRequest(t, router, "POST", "/verify", map[string]string{"email": email, "code": wrong})
		expected := 400
		if i == 5 {
			expected = 429
		}
		if r.Code != expected {
			t.Fatalf("attempt %d = %d", i, r.Code)
		}
	}
	if r := jsonRequest(t, router, "POST", "/verify", map[string]string{"email": email, "code": old}); r.Code != 400 {
		t.Fatal("locked code accepted")
	}
	cache.Delete("verify:cooldown:" + emailKey(email))
	if r := jsonRequest(t, router, "POST", "/resend", map[string]string{"email": email, "password": "strong-pass-123"}); r.Code != 202 {
		t.Fatalf("resend=%d", r.Code)
	}
	if r := jsonRequest(t, router, "POST", "/verify", map[string]string{"email": email, "code": mailer.code}); r.Code != 200 {
		t.Fatalf("new code=%d", r.Code)
	}
}

func TestVerificationCannotLoginBannedAccount(t *testing.T) {
	router, mailer := identityTestRouter(t)
	email := "banned@example.test"
	jsonRequest(t, router, "POST", "/register", map[string]string{"email": email, "username": "BannedUser", "password": "strong-pass-123"})
	database.DB.Model(&models.User{}).Where("email = ?", email).Update("account_status", "banned")
	r := jsonRequest(t, router, "POST", "/verify", map[string]string{"email": email, "code": mailer.code})
	if r.Code != 400 || bytes.Contains(r.Body.Bytes(), []byte("access_token")) {
		t.Fatalf("banned verify = %d", r.Code)
	}
}

func TestResendUniformResponseAndCooldownForUnknownAccount(t *testing.T) {
	router, mailer := identityTestRouter(t)
	r := jsonRequest(t, router, "POST", "/resend", map[string]string{"email": "unknown@example.test", "password": "strong-pass-123"})
	if r.Code != 401 || mailer.email != "" {
		t.Fatalf("unknown = %d", r.Code)
	}
	r = jsonRequest(t, router, "POST", "/resend", map[string]string{"email": "unknown@example.test", "password": "strong-pass-123"})
	if r.Code != 429 {
		t.Fatalf("unknown cooldown = %d", r.Code)
	}
}

func TestSMTPMissingAndRedisUnavailableFailClosed(t *testing.T) {
	for _, unavailable := range []string{"smtp", "redis"} {
		t.Run(unavailable, func(t *testing.T) {
			router, _ := identityTestRouter(t)
			if unavailable == "smtp" {
				authMailer = nil
			} else {
				dead := miniredis.RunT(t)
				cache.Connect(dead.Addr())
				dead.Close()
			}
			r := jsonRequest(t, router, "POST", "/register", map[string]string{"email": "failure@example.test", "username": "FailureUser", "password": "strong-pass-123"})
			if r.Code != 503 {
				t.Fatalf("unavailable = %d", r.Code)
			}
		})
	}
}

func TestFailedResendPreservesPreviouslyDeliveredCode(t *testing.T) {
	router, mailer := identityTestRouter(t)
	email := "preserve@example.test"
	jsonRequest(t, router, "POST", "/register", map[string]string{"email": email, "username": "PreserveUser", "password": "strong-pass-123"})
	previous := mailer.code
	cache.Delete("verify:cooldown:" + emailKey(email))
	mailer.err = errors.New("SMTP refused")
	r := jsonRequest(t, router, "POST", "/resend", map[string]string{"email": email, "password": "strong-pass-123"})
	if r.Code != 503 {
		t.Fatalf("resend=%d", r.Code)
	}
	r = jsonRequest(t, router, "POST", "/verify", map[string]string{"email": email, "code": previous})
	if r.Code != 200 {
		t.Fatalf("previous delivered code=%d", r.Code)
	}
}

func TestResendRejectsWrongPasswordWithoutSending(t *testing.T) {
	router, mailer := identityTestRouter(t)
	email := "password@example.test"
	jsonRequest(t, router, "POST", "/register", map[string]string{"email": email, "username": "PasswordUser", "password": "strong-pass-123"})
	cache.Delete("verify:cooldown:" + emailKey(email))
	mailer.email = ""
	r := jsonRequest(t, router, "POST", "/resend", map[string]string{"email": email, "password": "wrong-password"})
	if r.Code != 401 || mailer.email != "" {
		t.Fatalf("wrong credentials = %d", r.Code)
	}
}

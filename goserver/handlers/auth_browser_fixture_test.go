package handlers

// 仅 go test 显式启用的隔离 HTTP 夹具，不编译进生产服务。
import (
	"encoding/json"
	"errors"
	"net/http/httptest"
	"os"
	"strconv"
	"sync"
	"testing"
	"time"

	"github.com/alicebob/miniredis/v2"
	"github.com/gin-gonic/gin"
	"gorm.io/driver/sqlite"
	"gorm.io/gorm"
	"scwiki/server/cache"
	"scwiki/server/database"
	"scwiki/server/middleware"
	"scwiki/server/models"
)

type browserMailbox struct {
	sync.Mutex
	codes map[string]string
	fail  bool
}

func (m *browserMailbox) SendVerificationCode(email, code string) error {
	m.Lock()
	defer m.Unlock()
	if m.fail {
		return errors.New("isolated delivery failure")
	}
	m.codes[email] = code
	return nil
}
func (m *browserMailbox) SendPasswordChangeCode(email, code string) error {
	return m.SendVerificationCode(email, code)
}

func TestAuthBrowserFixture(t *testing.T) {
	file := os.Getenv("SCWIKI_AUTH_BROWSER_FIXTURE")
	if file == "" {
		t.Skip("explicit browser fixture only")
	}
	db, err := gorm.Open(sqlite.Open(":memory:"), &gorm.Config{})
	if err != nil {
		t.Fatal(err)
	}
	sql, _ := db.DB()
	sql.SetMaxOpenConns(1)
	defer sql.Close()
	if err = db.AutoMigrate(&models.User{}); err != nil {
		t.Fatal(err)
	}
	database.DB = db
	redis := miniredis.RunT(t)
	cache.Connect(redis.Addr())
	m := &browserMailbox{codes: map[string]string{}}
	authMailer = m
	verificationSecret = []byte("isolated-browser-auth-fixture")
	middleware.InitJWT(string(verificationSecret))
	gin.SetMode(gin.TestMode)
	r := gin.New()
	r.POST("/api/auth/register", registerHandler)
	r.POST("/api/auth/login", loginHandler)
	r.POST("/api/auth/verify-email", VerifyEmail)
	r.POST("/api/auth/resend-verification", ResendVerification)
	r.GET("/api/auth/username-availability", UsernameAvailability)
	r.POST("/api/auth/password-reset/request", RequestPasswordReset)
	r.POST("/api/auth/password-reset/verify", VerifyPasswordReset)
	r.POST("/api/auth/password-reset/complete", CompletePasswordReset)
	r.GET("/api/auth/me", middleware.AuthRequired, GetCurrentUser)
	r.GET("/__fixture/mail", func(c *gin.Context) {
		m.Lock()
		defer m.Unlock()
		c.JSON(200, gin.H{"code": m.codes[c.Query("email")]})
	})
	r.POST("/__fixture/fail-mail", func(c *gin.Context) { m.Lock(); defer m.Unlock(); m.fail = c.Query("enabled") == "1"; c.Status(204) })
	r.POST("/__fixture/advance", func(c *gin.Context) {
		n, _ := strconv.Atoi(c.Query("seconds"))
		redis.FastForward(time.Duration(n) * time.Second)
		c.Status(204)
	})
	server := httptest.NewServer(r)
	defer server.Close()
	data, _ := json.Marshal(gin.H{"url": server.URL, "database": "isolated SQLite", "cache": "isolated miniredis", "mail": "capturing Mailer interface; no external delivery"})
	if err := os.WriteFile(file, data, 0600); err != nil {
		t.Fatal(err)
	}
	defer os.Remove(file)
	deadline := time.After(8 * time.Minute)
	ticker := time.NewTicker(250 * time.Millisecond)
	defer ticker.Stop()
	for {
		select {
		case <-deadline:
			t.Fatal("browser fixture timed out")
		case <-ticker.C:
			if _, err := os.Stat(file + ".stop"); err == nil {
				os.Remove(file + ".stop")
				return
			}
		}
	}
}

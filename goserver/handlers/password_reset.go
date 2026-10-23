package handlers

import (
	"crypto/rand"
	"encoding/hex"
	"errors"
	"fmt"
	"strings"
	"time"
	"unicode/utf8"

	"github.com/gin-gonic/gin"
	"golang.org/x/crypto/bcrypt"
	"gorm.io/gorm"
	"gorm.io/gorm/clause"
	"scwiki/server/cache"
	"scwiki/server/database"
	"scwiki/server/models"
)

var errResetInvalid = errors.New("invalid reset challenge")
var errResetLocked = errors.New("reset attempts exceeded")
var errResetUnavailable = errors.New("reset cache unavailable")

func resetScope(user models.User) string {
	return fmt.Sprintf("password-reset:%d:%d:%s", user.ID, user.SessionVersion, emailKey(user.Email))
}

func resetEligible(user models.User) bool {
	return user.IsEmailVerified && (user.AccountStatus == "active" || user.AccountStatus == "")
}

// 对公开验证码/令牌验证同时限制邮箱和 IP；不存在的账号同样计数。
func resetAttemptAllowed(c *gin.Context, email string) bool {
	for _, key := range []string{"password-reset:attempt:email:" + emailKey(email), "password-reset:attempt:ip:" + emailKey(c.ClientIP())} {
		n, err := cache.IncrementWindow(key, verificationTTL)
		if err != nil {
			resetFailure(c, errResetUnavailable, false)
			return false
		}
		if n > 40 {
			c.Header("Retry-After", "300")
			c.JSON(429, gin.H{"code": "verification_rate_limited", "resend_after_seconds": 300})
			return false
		}
	}
	return true
}

func resetFailure(c *gin.Context, err error, grant bool) {
	code := "invalid_verification_code"
	if grant {
		code = "invalid_reset_token"
	}
	switch {
	case errors.Is(err, errResetInvalid), errors.Is(err, gorm.ErrRecordNotFound):
		c.JSON(400, gin.H{"code": code, "error": "验证无效或已过期，请重新获取"})
	case errors.Is(err, errResetLocked):
		c.JSON(429, gin.H{"code": "verification_attempts_exceeded", "error": "尝试次数已用完，请重新获取"})
	default:
		c.JSON(503, gin.H{"code": "verification_unavailable", "error": "验证服务暂不可用，请重新获取验证码"})
	}
}

func consumeReset(scope, secret string) error {
	status, err := cache.ConsumeVerificationCode("verify:code:"+scope, "verify:attempts:"+scope, verificationDigest(scope, secret), 5, verificationTTL)
	if err != nil {
		return errResetUnavailable
	}
	if status == "locked" {
		return errResetLocked
	}
	if status != "valid" {
		return errResetInvalid
	}
	return nil
}

func RequestPasswordReset(c *gin.Context) {
	var body struct {
		Email string `json:"email"`
	}
	if c.ShouldBindJSON(&body) != nil || !validRegistrationEmail(normalizeEmail(body.Email)) {
		c.JSON(400, gin.H{"code": "invalid_email"})
		return
	}
	body.Email = normalizeEmail(body.Email)
	if !mailConfigured() {
		verificationSendError(c, 0, errResetUnavailable, false)
		return
	}
	retry, err := checkSendLimits(body.Email, c.ClientIP())
	if verificationSendError(c, retry, err, false) {
		return
	}
	// 邮件、验证码发布及旧授权撤销在同一账号行锁中，与验证/改密串行。
	err = database.DB.Transaction(func(tx *gorm.DB) error {
		var user models.User
		err := tx.Clauses(clause.Locking{Strength: "UPDATE"}).Where("email = ?", body.Email).First(&user).Error
		if errors.Is(err, gorm.ErrRecordNotFound) {
			return nil
		}
		if err != nil {
			return err
		}
		if !resetEligible(user) {
			return nil
		}
		code, err := verificationCode()
		if err != nil {
			return err
		}
		if err = authMailer.SendPasswordChangeCode(user.Email, code); err != nil {
			return err
		}
		scope := resetScope(user)
		if err = cache.Delete("verify:code:"+scope+":grant", "verify:attempts:"+scope+":grant"); err != nil {
			return err
		}
		return cache.PublishVerificationCode(scope, verificationDigest(scope, code), verificationTTL)
	})
	if verificationSendError(c, 0, err, false) {
		return
	}
	c.JSON(202, gin.H{"message": "如果该邮箱已注册且可用，将收到验证码", "resend_after_seconds": 60, "expires_in_seconds": 300})
}

func VerifyPasswordReset(c *gin.Context) {
	var body struct {
		Email string `json:"email"`
		Code  string `json:"code"`
	}
	if c.ShouldBindJSON(&body) != nil || !validRegistrationEmail(normalizeEmail(body.Email)) || len(body.Code) != 6 || strings.IndexFunc(body.Code, func(r rune) bool { return r < '0' || r > '9' }) >= 0 {
		resetFailure(c, errResetInvalid, false)
		return
	}
	body.Email = normalizeEmail(body.Email)
	if !resetAttemptAllowed(c, body.Email) {
		return
	}
	secret := make([]byte, 32)
	if _, err := rand.Read(secret); err != nil {
		resetFailure(c, err, false)
		return
	}
	token := hex.EncodeToString(secret)
	err := database.DB.Transaction(func(tx *gorm.DB) error {
		var user models.User
		if err := tx.Clauses(clause.Locking{Strength: "UPDATE"}).Where("email = ?", body.Email).First(&user).Error; err != nil {
			return err
		}
		if !resetEligible(user) {
			return errResetInvalid
		}
		scope := resetScope(user)
		if err := consumeReset(scope, body.Code); err != nil {
			return err
		}
		return cache.PublishVerificationCode(scope+":grant", verificationDigest(scope+":grant", token), verificationTTL)
	})
	if err != nil {
		resetFailure(c, err, false)
		return
	}
	c.Header("Cache-Control", "no-store")
	c.JSON(200, gin.H{"reset_token": token, "expires_in_seconds": 300})
}

func CompletePasswordReset(c *gin.Context) {
	var body struct {
		Email    string `json:"email"`
		Token    string `json:"reset_token"`
		Password string `json:"new_password"`
	}
	if c.ShouldBindJSON(&body) != nil || !validRegistrationEmail(normalizeEmail(body.Email)) || len(body.Token) != 64 {
		resetFailure(c, errResetInvalid, true)
		return
	}
	if utf8.RuneCountInString(body.Password) < 10 || len(body.Password) > 72 {
		c.JSON(400, gin.H{"code": "invalid_password", "error": "密码至少 10 个字符，最多 72 字节"})
		return
	}
	body.Email = normalizeEmail(body.Email)
	if !resetAttemptAllowed(c, body.Email) {
		return
	}
	err := database.DB.Transaction(func(tx *gorm.DB) error {
		var user models.User
		if err := tx.Clauses(clause.Locking{Strength: "UPDATE"}).Where("email = ?", body.Email).First(&user).Error; err != nil {
			return err
		}
		if !resetEligible(user) {
			return errResetInvalid
		}
		if err := consumeReset(resetScope(user)+":grant", body.Token); err != nil {
			return err
		}
		hash, err := bcrypt.GenerateFromPassword([]byte(body.Password), bcrypt.DefaultCost)
		if err != nil {
			return err
		}
		return tx.Model(&user).Updates(map[string]any{"password_hash": string(hash), "session_version": gorm.Expr("session_version + 1"), "updated_at": time.Now()}).Error
	})
	if err != nil {
		resetFailure(c, err, true)
		return
	}
	c.Status(204)
}

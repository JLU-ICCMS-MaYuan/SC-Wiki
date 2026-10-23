package handlers

import (
	"errors"
	"fmt"
	"strings"
	"time"

	"scwiki/server/cache"
	"scwiki/server/database"
	"scwiki/server/models"

	"github.com/gin-gonic/gin"
	"golang.org/x/crypto/bcrypt"
	"gorm.io/gorm"
	"gorm.io/gorm/clause"
)

// 与注册隔离；会话版本或邮箱变化后，所有旧改密码自然失效。
func passwordCodeScope(user models.User) string {
	return fmt.Sprintf("password-change:%d:%d:%s", user.ID, user.SessionVersion, emailKey(user.Email))
}

// 保留认证中间件核验过的会话快照，事务内与最新行比较，拒绝并发撤销的旧会话。
func passwordCurrentUser(c *gin.Context) (*models.User, bool) {
	value, exists := c.Get("current_user")
	user, valid := value.(*models.User)
	if !exists || !valid || user == nil {
		c.JSON(401, gin.H{"error": "未登录"})
		return nil, false
	}
	return user, true
}

func passwordIdentityValid(user models.User, email, password string) bool {
	return normalizeEmail(email) == normalizeEmail(user.Email) &&
		(user.AccountStatus == "" || user.AccountStatus == "active") &&
		bcrypt.CompareHashAndPassword([]byte(user.PasswordHash), []byte(password)) == nil
}

// 身份校验失败也受服务端额度约束，不能通过直接请求绕过 UI。
func passwordAttemptAllowed(c *gin.Context, user models.User) bool {
	for _, key := range []string{fmt.Sprintf("password-change:identity:user:%d", user.ID), "password-change:identity:ip:" + emailKey(c.ClientIP())} {
		count, err := cache.IncrementWindow(key, 5*time.Minute)
		if err != nil {
			c.JSON(503, gin.H{"error": "验证服务暂不可用"})
			return false
		}
		if count > 20 {
			c.JSON(429, gin.H{"error": "请求过于频繁，请稍后再试", "resend_after_seconds": 300})
			return false
		}
	}
	return true
}

func SendPasswordChangeCode(c *gin.Context) {
	user, ok := passwordCurrentUser(c)
	if !ok {
		return
	}
	var body struct {
		CurrentPassword string `json:"current_password"`
		Email           string `json:"email"`
	}
	if c.ShouldBindJSON(&body) != nil || body.CurrentPassword == "" || !validRegistrationEmail(normalizeEmail(body.Email)) {
		c.JSON(400, gin.H{"error": "请填写旧密码和有效的绑定邮箱"})
		return
	}
	if !passwordAttemptAllowed(c, *user) {
		return
	}
	if !passwordIdentityValid(*user, body.Email, body.CurrentPassword) {
		c.JSON(403, gin.H{"error": "旧密码或绑定邮箱不正确"})
		return
	}
	if !mailConfigured() {
		verificationSendError(c, 0, errors.New("SMTP unavailable"), false)
		return
	}
	retry, err := checkSendLimits(user.Email, c.ClientIP())
	if verificationSendError(c, retry, err, false) {
		return
	}
	code, err := verificationCode()
	if err == nil {
		err = authMailer.SendPasswordChangeCode(user.Email, code)
	}
	if err == nil {
		scope := passwordCodeScope(*user)
		err = cache.PublishVerificationCode(scope, verificationDigest(scope, code), verificationTTL)
	}
	if verificationSendError(c, 0, err, false) {
		return
	}
	c.JSON(202, gin.H{"resend_after_seconds": 60, "expires_in_seconds": 300})
}

func ChangePassword(c *gin.Context) {
	user, ok := passwordCurrentUser(c)
	if !ok {
		return
	}
	var body struct {
		CurrentPassword string `json:"current_password"`
		Email           string `json:"email"`
		Code            string `json:"code"`
		NewPassword     string `json:"new_password"`
	}
	if c.ShouldBindJSON(&body) != nil || len(body.NewPassword) < 10 || len(body.NewPassword) > 72 || len(body.Code) != 6 || strings.IndexFunc(body.Code, func(r rune) bool { return r < '0' || r > '9' }) >= 0 || body.Email == "" || body.CurrentPassword == "" {
		c.JSON(400, gin.H{"error": "请填写旧密码、绑定邮箱、六位验证码和 10–72 字节的新密码"})
		return
	}
	if !passwordAttemptAllowed(c, *user) {
		return
	}
	if body.NewPassword == body.CurrentPassword {
		c.JSON(400, gin.H{"error": "新密码不能与旧密码相同"})
		return
	}
	invalidIdentity := errors.New("invalid identity")
	invalidCode := errors.New("invalid code")
	unavailable := errors.New("verification unavailable")
	lockedCode := errors.New("verification locked")
	err := database.DB.Transaction(func(tx *gorm.DB) error {
		var locked models.User
		if err := tx.Clauses(clause.Locking{Strength: "UPDATE"}).First(&locked, user.ID).Error; err != nil {
			return err
		}
		if locked.SessionVersion != user.SessionVersion || !passwordIdentityValid(locked, body.Email, body.CurrentPassword) {
			return invalidIdentity
		}
		scope := passwordCodeScope(locked)
		status, err := cache.ConsumeVerificationCode("verify:code:"+scope, "verify:attempts:"+scope, verificationDigest(scope, body.Code), 5, verificationTTL)
		if err != nil {
			return unavailable
		}
		if status == "locked" {
			return lockedCode
		}
		if status != "valid" {
			return invalidCode
		}
		hash, err := bcrypt.GenerateFromPassword([]byte(body.NewPassword), bcrypt.DefaultCost)
		if err != nil {
			return err
		}
		return tx.Model(&locked).Updates(map[string]any{"password_hash": string(hash), "session_version": gorm.Expr("session_version + 1"), "updated_at": time.Now()}).Error
	})
	switch err {
	case nil:
		c.Status(204)
	case invalidIdentity:
		c.JSON(403, gin.H{"error": "旧密码或绑定邮箱不正确，或登录已失效"})
	case invalidCode:
		c.JSON(400, gin.H{"error": "验证码无效或已过期，请重新获取", "code": "invalid_verification_code"})
	case lockedCode:
		c.JSON(429, gin.H{"error": "验证码尝试次数已用完，请重新获取", "code": "verification_attempts_exceeded"})
	case unavailable:
		c.JSON(503, gin.H{"error": "验证服务暂不可用"})
	default:
		c.JSON(500, gin.H{"error": "密码修改失败，请重新获取验证码"})
	}
}

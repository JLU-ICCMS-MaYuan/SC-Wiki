package handlers

import (
	"crypto/hmac"
	cryptorand "crypto/rand"
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"log"
	"math/big"
	"net/http"
	"net/mail"
	"os"
	"strings"
	"time"

	"scwiki/server/cache"
	"scwiki/server/config"
	"scwiki/server/database"
	"scwiki/server/middleware"
	"scwiki/server/models"
	"scwiki/server/services"

	"github.com/gin-gonic/gin"
	"golang.org/x/crypto/bcrypt"
	"gorm.io/gorm"
)

const verificationTTL = 5 * time.Minute

// 不存在的账号也执行同成本校验，避免重发接口暴露账号状态。
var unknownAccountHash = func() []byte {
	hash, err := bcrypt.GenerateFromPassword([]byte("unusable-account-placeholder"), bcrypt.DefaultCost)
	if err != nil {
		panic(err)
	}
	return hash
}()

var (
	authMailer         services.Mailer
	verificationSecret []byte
	avatarDir          string
)

func ConfigureAuth(cfg config.Config) {
	authMailer = services.NewSMTPMailer(services.EmailConfig{
		Host: cfg.SMTPHost, Port: cfg.SMTPPort, Username: cfg.SMTPUsername,
		Password: cfg.SMTPPassword, From: cfg.SMTPFrom, TLSMode: cfg.SMTPTLSMode,
	})
	verificationSecret = []byte(cfg.JWTSecret)
	avatarDir = cfg.AvatarDir
	_ = os.MkdirAll(avatarDir, 0o750)
}

func normalizeEmail(email string) string { return strings.ToLower(strings.TrimSpace(email)) }

func emailKey(email string) string {
	sum := sha256.Sum256([]byte(normalizeEmail(email)))
	return hex.EncodeToString(sum[:])
}

func verificationDigest(email, code string) string {
	mac := hmac.New(sha256.New, verificationSecret)
	mac.Write([]byte(normalizeEmail(email)))
	mac.Write([]byte{0})
	mac.Write([]byte(code))
	return hex.EncodeToString(mac.Sum(nil))
}

func verificationCode() (string, error) {
	n, err := cryptorand.Int(cryptorand.Reader, big.NewInt(1_000_000))
	if err != nil {
		return "", err
	}
	return fmt.Sprintf("%06d", n.Int64()), nil
}

func validRegistrationEmail(email string) bool {
	address, err := mail.ParseAddress(email)
	return err == nil && address.Address == email && !strings.ContainsAny(email, "\r\n")
}

func checkSendLimits(email, ip string) (int, error) {
	return cache.ReserveVerificationSend(emailKey(email), emailKey(ip), time.Now())
}

func mailConfigured() bool {
	if authMailer == nil {
		return false
	}
	if sender, ok := authMailer.(*services.SMTPMailer); ok {
		return sender.Configured()
	}
	return true
}

func deliverVerification(email string) error {
	code, err := verificationCode()
	if err != nil {
		return err
	}
	if err := authMailer.SendVerificationCode(email, code); err != nil {
		return err
	}
	return cache.PublishVerificationCode(emailKey(email), verificationDigest(email, code), verificationTTL)
}

func verificationSendError(c *gin.Context, retry int, err error, pending bool) bool {
	if err == nil && retry == 0 {
		return false
	}
	body := gin.H{"requires_email_verification": pending}
	if retry > 0 {
		c.Header("Retry-After", fmt.Sprint(retry))
		body["error"], body["code"], body["resend_after_seconds"] = "请求过于频繁", "verification_rate_limited", retry
		c.JSON(429, body)
	} else {
		body["error"], body["code"] = "验证码发送失败，请稍后重试", "verification_send_failed"
		body["resend_after_seconds"] = 60
		c.JSON(503, body)
	}
	return true
}

func loginHandler(c *gin.Context) {
	var body struct{ Email, Password string }
	if c.ShouldBindJSON(&body) != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "参数错误"})
		return
	}
	var user models.User
	if database.DB.Where("email = ?", normalizeEmail(body.Email)).First(&user).Error != nil ||
		bcrypt.CompareHashAndPassword([]byte(user.PasswordHash), []byte(body.Password)) != nil {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "邮箱或密码错误"})
		return
	}
	if user.AccountStatus != "" && user.AccountStatus != "active" {
		c.JSON(http.StatusForbidden, gin.H{"error": "账号不可用", "code": "account_inactive"})
		return
	}
	if !user.IsEmailVerified {
		c.JSON(403, gin.H{"error": "邮箱未验证，请先完成邮箱验证", "code": "email_not_verified"})
		return
	}
	token, err := middleware.GenerateTokenForUser(user)
	if err != nil {
		c.JSON(500, gin.H{"error": "生成 token 失败"})
		return
	}
	c.JSON(http.StatusOK, gin.H{"access_token": token, "token_type": "bearer", "user": clientUserPayload(user)})
}

func registerHandler(c *gin.Context) {
	var body struct {
		Email    string `json:"email"`
		Password string `json:"password"`
		Username string `json:"username"`
		RealName string `json:"real_name"`
	}
	if c.ShouldBindJSON(&body) != nil || body.Email == "" || body.Username == "" || len(body.Password) < 10 {
		c.JSON(http.StatusBadRequest, gin.H{"error": "邮箱、用户名不能为空，密码至少 10 位"})
		return
	}
	body.Email = normalizeEmail(body.Email)
	if !validRegistrationEmail(body.Email) {
		c.JSON(400, gin.H{"error": "邮箱格式错误", "code": "invalid_email"})
		return
	}
	if err := validatePublicUsername(body.Username); err != nil {
		c.JSON(400, gin.H{"error": err.Error()})
		return
	}
	var existing models.User
	err := database.DB.Where("email = ?", body.Email).First(&existing).Error
	if err == nil {
		c.JSON(409, gin.H{"error": "该邮箱已注册"})
		return
	}
	if err != gorm.ErrRecordNotFound {
		c.JSON(500, gin.H{"error": "注册失败"})
		return
	}
	available, err := usernameAvailable(database.DB, body.Username, 0)
	if err != nil {
		c.JSON(500, gin.H{"error": "用户名检查失败"})
		return
	}
	if !available {
		c.JSON(409, gin.H{"error": errUsernameTaken.Error()})
		return
	}
	hash, err := bcrypt.GenerateFromPassword([]byte(body.Password), bcrypt.DefaultCost)
	if err != nil {
		c.JSON(500, gin.H{"error": "密码加密失败"})
		return
	}
	user := models.User{Email: body.Email, Username: body.Username, PasswordHash: string(hash), RealName: strings.TrimSpace(body.RealName), Role: "user", IsApproved: true, IsEmailVerified: false, AccountStatus: "active"}
	if err := database.DB.Create(&user).Error; err != nil {
		if isDuplicateKeyError(err) {
			c.JSON(409, gin.H{"error": "邮箱或用户名已被占用"})
			return
		}
		log.Printf("注册用户写入数据库失败: %v", err)
		c.JSON(500, gin.H{"error": "注册失败"})
		return
	}
	if !mailConfigured() {
		verificationSendError(c, 0, fmt.Errorf("SMTP 未配置"), true)
		return
	}
	retry, sendErr := checkSendLimits(body.Email, c.ClientIP())
	if verificationSendError(c, retry, sendErr, true) {
		return
	}
	if verificationSendError(c, 0, deliverVerification(body.Email), true) {
		return
	}
	c.JSON(http.StatusAccepted, gin.H{"requires_email_verification": true, "resend_after_seconds": 60})
}

func VerifyEmail(c *gin.Context) {
	var body struct {
		Email string `json:"email"`
		Code  string `json:"code"`
	}
	if c.ShouldBindJSON(&body) != nil || len(body.Code) != 6 || strings.IndexFunc(body.Code, func(r rune) bool { return r < '0' || r > '9' }) >= 0 {
		c.JSON(400, gin.H{"error": "验证码无效", "code": "invalid_verification_code"})
		return
	}
	body.Email = normalizeEmail(body.Email)
	var user models.User
	lookupErr := database.DB.Where("email = ?", body.Email).First(&user).Error
	if lookupErr != nil && lookupErr != gorm.ErrRecordNotFound {
		c.JSON(503, gin.H{"error": "验证服务暂不可用", "code": "verification_unavailable"})
		return
	}
	if lookupErr != nil || user.IsEmailVerified || (user.AccountStatus != "" && user.AccountStatus != "active") {
		c.JSON(400, gin.H{"error": "验证码无效或已过期", "code": "invalid_verification_code"})
		return
	}
	status, err := cache.ConsumeVerificationCode("verify:code:"+emailKey(body.Email), "verify:attempts:"+emailKey(body.Email), verificationDigest(body.Email, body.Code), 5, verificationTTL)
	if err != nil {
		c.JSON(503, gin.H{"error": "验证服务暂不可用"})
		return
	}
	if status != "valid" {
		if status == "locked" {
			c.JSON(429, gin.H{"error": "验证码尝试次数已用完，请重新获取", "code": "verification_attempts_exceeded"})
		} else {
			c.JSON(400, gin.H{"error": "验证码无效或已过期", "code": "invalid_verification_code"})
		}
		return
	}
	result := database.DB.Model(&user).Where("is_email_verified = ? AND account_status = ?", false, "active").Updates(map[string]any{"is_email_verified": true, "is_approved": true})
	if result.Error != nil || result.RowsAffected != 1 {
		c.JSON(503, gin.H{"error": "验证失败，请重新获取验证码", "code": "verification_unavailable"})
		return
	}
	user.IsEmailVerified, user.IsApproved = true, true
	token, err := middleware.GenerateTokenForUser(user)
	if err != nil {
		c.JSON(500, gin.H{"error": "生成 token 失败"})
		return
	}
	c.JSON(200, gin.H{"access_token": token, "token_type": "bearer", "user": clientUserPayload(user)})
}

func ResendVerification(c *gin.Context) {
	var body struct {
		Email    string `json:"email"`
		Password string `json:"password"`
	}
	if c.ShouldBindJSON(&body) != nil || !validRegistrationEmail(normalizeEmail(body.Email)) {
		c.JSON(400, gin.H{"error": "邮箱格式错误", "code": "invalid_email"})
		return
	}
	if !mailConfigured() {
		verificationSendError(c, 0, fmt.Errorf("SMTP 未配置"), false)
		return
	}
	email := normalizeEmail(body.Email)
	retry, err := checkSendLimits(email, c.ClientIP())
	if verificationSendError(c, retry, err, false) {
		return
	}
	var user models.User
	err = database.DB.Where("email = ?", email).First(&user).Error
	if err != nil && err != gorm.ErrRecordNotFound {
		verificationSendError(c, 0, err, false)
		return
	}
	hash := unknownAccountHash
	if err == nil {
		hash = []byte(user.PasswordHash)
	}
	passwordErr := bcrypt.CompareHashAndPassword(hash, []byte(body.Password))
	if err != nil || passwordErr != nil {
		c.JSON(401, gin.H{"error": "邮箱或密码错误", "code": "invalid_credentials"})
		return
	}
	if !user.IsEmailVerified && user.AccountStatus == "active" {
		if verificationSendError(c, 0, deliverVerification(email), false) {
			return
		}
	}
	c.JSON(202, gin.H{"message": "如果邮箱可验证，验证码将发送", "resend_after_seconds": 60})
}

func GetCurrentUser(c *gin.Context) {
	value, ok := c.Get("current_user")
	if !ok {
		c.JSON(401, gin.H{"error": "未登录"})
		return
	}
	c.JSON(200, gin.H{"user": clientUserPayload(*value.(*models.User))})
}

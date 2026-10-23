package handlers

import (
	"strings"
	"testing"

	"github.com/gin-gonic/gin"
	mysqldriver "github.com/go-sql-driver/mysql"
	"gorm.io/gorm"
	"scwiki/server/database"
	"scwiki/server/models"
)

func TestRegistrationRejectsDuplicateUsername(t *testing.T) {
	router, mailer := identityTestRouter(t)
	router.GET("/available", UsernameAvailability)
	user := models.User{Email: "existing@example.test", Username: "ExistingUser", PasswordHash: "unused", AccountStatus: "active"}
	if err := database.DB.Create(&user).Error; err != nil {
		t.Fatal(err)
	}
	available := jsonRequest(t, router, "GET", "/available?username=ExistingUser", nil)
	if available.Code != 200 || !strings.Contains(available.Body.String(), `"available":false`) {
		t.Fatal(available.Code, available.Body)
	}
	if strings.Contains(available.Body.String(), user.Email) {
		t.Fatal("availability leaked account information")
	}
	response := jsonRequest(t, router, "POST", "/register", gin.H{"email": "another@example.test", "username": user.Username, "password": "longPassword123"})
	if response.Code != 409 || !strings.Contains(response.Body.String(), "用户名已被占用") {
		t.Fatal(response.Code, response.Body)
	}
	var count int64
	database.DB.Model(&models.User{}).Count(&count)
	if count != 1 || mailer.code != "" {
		t.Fatal("duplicate created an account or sent mail")
	}
	// 绕过处理器直接写入也必须被真实测试数据库的唯一索引拒绝。
	duplicate := models.User{Email: "direct@example.test", Username: user.Username, PasswordHash: "unused"}
	if err := database.DB.Create(&duplicate).Error; err == nil {
		t.Fatal("database accepted duplicate username")
	}
}

func TestRegistrationMapsConcurrentUsernameConflict(t *testing.T) {
	router, mailer := identityTestRouter(t)
	// 模拟“预检查通过、落库前被另一请求占用”的 MySQL 1062 错误边界。
	if err := database.DB.Callback().Create().Before("gorm:create").Register("test:concurrent-username", func(tx *gorm.DB) {
		tx.AddError(&mysqldriver.MySQLError{Number: 1062, Message: "duplicate username"})
	}); err != nil {
		t.Fatal(err)
	}
	response := jsonRequest(t, router, "POST", "/register", gin.H{"email": "race@example.test", "username": "RaceUser", "password": "longPassword123"})
	if response.Code != 409 || !strings.Contains(response.Body.String(), "邮箱或用户名已被占用") || mailer.code != "" {
		t.Fatal(response.Code, response.Body)
	}
}

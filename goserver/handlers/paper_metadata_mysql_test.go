package handlers

import (
	"bytes"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
	"strings"
	"testing"

	"scwiki/server/database"
	"scwiki/server/middleware"
	"scwiki/server/models"

	"github.com/gin-gonic/gin"
	"gorm.io/driver/mysql"
	"gorm.io/gorm"
	"gorm.io/gorm/logger"
)

// 使用当前 MySQL 的外层事务；实际管理员处理器及历史写入都在事务内回滚。
func TestCurrentMySQLPaperMetadata(t *testing.T) {
	if os.Getenv("SCWIKI_CURRENT_MYSQL") != "1" {
		t.Skip("需要显式选择当前 MySQL")
	}
	db, err := gorm.Open(mysql.Open(os.Getenv("SCWIKI_TEST_MYSQL_DSN")), &gorm.Config{Logger: logger.Default.LogMode(logger.Silent)})
	if err != nil {
		t.Fatal("连接当前 MySQL 失败")
	}
	sqlDB, _ := db.DB()
	defer sqlDB.Close()
	tx := db.Begin()
	if tx.Error != nil {
		t.Fatal(tx.Error)
	}
	previous := database.DB
	database.DB = tx
	defer func() { tx.Rollback(); database.DB = previous }()
	var actor models.User
	if err := tx.Where("role IN ? AND account_status = ?", []string{"admin", "superadmin"}, "active").First(&actor).Error; err != nil {
		t.Fatal(err)
	}
	year := 2026
	paper := models.Paper{Title: strPtr("Issue 99 书目验证"), Year: &year, Pages: strPtr("100-108"), ContentRevision: 1, ReviewStatus: "pending"}
	if err := tx.Create(&paper).Error; err != nil {
		t.Fatal(err)
	}
	middleware.InitJWT("issue99-local-transaction-test")
	token, err := middleware.GenerateTokenForUser(actor)
	if err != nil {
		t.Fatal(err)
	}
	gin.SetMode(gin.TestMode)
	router := gin.New()
	router.PUT("/api/admin/papers/:id", middleware.AuthRequired, middleware.AdminRequired, UpdatePaper)
	router.GET("/api/admin/papers/:id", middleware.AuthRequired, middleware.AdminRequired, GetPaperDetail)
	path := fmt.Sprintf("/api/admin/papers/%d", paper.ID)
	request := func(method string, payload map[string]interface{}) *httptest.ResponseRecorder {
		raw, _ := json.Marshal(payload)
		req := httptest.NewRequest(method, path, bytes.NewReader(raw))
		req.Header.Set("Content-Type", "application/json")
		req.Header.Set("Authorization", "Bearer "+token)
		response := httptest.NewRecorder()
		router.ServeHTTP(response, req)
		return response
	}
	check := func(expected interface{}) {
		response := request(http.MethodGet, nil)
		if response.Code != 200 {
			t.Fatalf("详情失败：%s", response.Body.String())
		}
		var detail map[string]interface{}
		if err := json.Unmarshal(response.Body.Bytes(), &detail); err != nil {
			t.Fatal(err)
		}
		if detail["issue_number"] != expected || detail["pages"] != "100-108" {
			t.Fatalf("书目信息丢失：%v / %v", detail["issue_number"], detail["pages"])
		}
	}
	check(nil)
	for _, value := range []interface{}{"S1", "3-4", "", nil} {
		response := request(http.MethodPut, map[string]interface{}{"issue_number": value})
		if response.Code != 200 {
			t.Fatalf("保存失败：%s", response.Body.String())
		}
		check(value)
	}
	for _, value := range []interface{}{123, strings.Repeat("期", 101)} {
		if response := request(http.MethodPut, map[string]interface{}{"issue_number": value}); response.Code != 400 {
			t.Fatalf("非法期号未拒绝：%d", response.Code)
		}
	}
	if err := tx.Rollback().Error; err != nil {
		t.Fatal(err)
	}
	var count int64
	if err := db.Model(&models.Paper{}).Where("id = ?", paper.ID).Count(&count).Error; err != nil || count != 0 {
		t.Fatal("测试论文未回滚")
	}
}

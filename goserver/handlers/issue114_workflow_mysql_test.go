package handlers

import (
	"bytes"
	"net/http"
	"net/http/httptest"
	"os"
	"strings"
	"testing"

	"github.com/gin-gonic/gin"
	"gorm.io/driver/mysql"
	"gorm.io/gorm"
	"scwiki/server/database"
	"scwiki/server/middleware"
	"scwiki/server/models"
)

// Python 隔离工作流提供论文；真实 JWT、审核事务与 Python 来源门禁共同验收。
func TestIssue114DocumentReview(t *testing.T) {
	paperID := os.Getenv("ISSUE114_REVIEW_PAPER")
	if paperID == "" {
		t.Skip("需要 #114 隔离工作流样本")
	}
	dsn := os.Getenv("ISSUE114_MYSQL_DSN")
	if !strings.Contains(dsn, "@unix(/tmp/issue114-workflow-") || !strings.Contains(dsn, "/test_issue114_workflow?") {
		t.Fatal("仅允许专用临时 Unix socket 测试库")
	}
	db, err := gorm.Open(mysql.Open(dsn), &gorm.Config{})
	if err != nil {
		t.Fatal(err)
	}
	sqlDB, _ := db.DB()
	defer sqlDB.Close()
	previous := database.DB
	database.DB = db
	defer func() { database.DB = previous }()
	var admin, owner models.User
	if err = db.First(&admin, os.Getenv("ISSUE114_REVIEW_ADMIN")).Error; err != nil {
		t.Fatal(err)
	}
	if err = db.First(&owner, os.Getenv("ISSUE114_REVIEW_OWNER")).Error; err != nil {
		t.Fatal(err)
	}
	middleware.InitJWT(os.Getenv("JWT_SECRET_KEY"))
	adminToken, err := middleware.GenerateTokenForUser(admin)
	if err != nil {
		t.Fatal(err)
	}
	ownerToken, err := middleware.GenerateTokenForUser(owner)
	if err != nil {
		t.Fatal(err)
	}
	gin.SetMode(gin.TestMode)
	router := gin.New()
	router.POST("/api/admin/papers/:id/review", middleware.AuthRequired, middleware.AdminRequired, ReviewPaper)
	review := func(token string) *httptest.ResponseRecorder {
		req := httptest.NewRequest(http.MethodPost, "/api/admin/papers/"+paperID+"/review",
			bytes.NewBufferString(os.Getenv("ISSUE114_REVIEW_BODY")))
		req.Header.Set("Authorization", "Bearer "+token)
		req.Header.Set("Content-Type", "application/json")
		response := httptest.NewRecorder()
		router.ServeHTTP(response, req)
		return response
	}
	if response := review(ownerToken); response.Code != 403 {
		t.Fatalf("上传者不能批准或拒绝自己的论文：%d %s", response.Code, response.Body.String())
	}
	if response := review(adminToken); response.Code != 200 {
		t.Fatalf("真实审核失败：%d %s", response.Code, response.Body.String())
	}
	var paper models.Paper
	if err := db.First(&paper, paperID).Error; err != nil {
		t.Fatal(err)
	}
	if paper.ReviewStatus != os.Getenv("ISSUE114_REVIEW_STATUS") {
		t.Fatal("审核状态未持久化")
	}
	var count int64
	db.Model(&models.PaperEvidenceLocator{}).Where("paper_id = ? AND paper_revision = ?", paper.ID, paper.ContentRevision).Count(&count)
	if count < 2 {
		t.Fatal("审核后当前区域证据丢失")
	}
}

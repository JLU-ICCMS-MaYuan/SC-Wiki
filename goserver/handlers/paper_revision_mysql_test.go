package handlers

import (
	"bytes"
	"fmt"
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

// 由 Python 的真实返修事务创建隔离样本；真实鉴权与审核，仅截断事务外索引/文件清理。
func TestRevisionResubmittedReview(t *testing.T) {
	id := os.Getenv("SCWIKI_REVISION_TEST_PAPER")
	if id == "" {
		t.Skip("由 test_paper_revisions.py 提供返修后的隔离样本")
	}
	dsn := os.Getenv("SCWIKI_TEST_MYSQL_DSN")
	if !strings.Contains(dsn, "test") || !strings.Contains(dsn, "127.0.0.1") {
		t.Fatal("仅允许隔离本地测试库")
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
	var paper models.Paper
	if err := db.First(&paper, id).Error; err != nil {
		t.Fatal(err)
	}
	if paper.ReviewStatus != "pending" || paper.ContentRevision != 2 {
		t.Fatal("返修未生成待审第二版")
	}
	var admin, owner models.User
	if err := db.First(&admin, os.Getenv("SCWIKI_REVISION_TEST_ADMIN")).Error; err != nil {
		t.Fatal(err)
	}
	if err := db.First(&owner, *paper.UploadedBy).Error; err != nil {
		t.Fatal(err)
	}
	if paperForViewer(paper, &owner)["can_revise"] != false {
		t.Fatal("送审后仍可返修")
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
	service := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"ok":true}`))
	}))
	defer service.Close()
	t.Setenv("PYTHON_BACKEND_URL", service.URL)
	gin.SetMode(gin.TestMode)
	router := gin.New()
	router.POST("/api/admin/papers/:id/review", middleware.AuthRequired, middleware.AdminRequired, ReviewPaper)
	router.PATCH("/api/papers/:id", middleware.AuthRequired, PatchPaper)
	review := func(token string) *httptest.ResponseRecorder {
		req := httptest.NewRequest(http.MethodPost, fmt.Sprintf("/api/admin/papers/%s/review", id),
			bytes.NewBufferString(fmt.Sprintf(`{"status":"rejected","comment":"返修后再次核对","review_request_id":"revision-review-%s"}`, id)))
		req.Header.Set("Authorization", "Bearer "+token)
		req.Header.Set("Content-Type", "application/json")
		response := httptest.NewRecorder()
		router.ServeHTTP(response, req)
		return response
	}
	if response := review(ownerToken); response.Code != 403 {
		t.Fatalf("上传者审核越权：%d %s", response.Code, response.Body.String())
	}
	if response := review(adminToken); response.Code != 200 {
		t.Fatalf("再次审核失败：%d %s", response.Code, response.Body.String())
	}
	if err := db.First(&paper, id).Error; err != nil {
		t.Fatal(err)
	}
	if paper.ReviewStatus != "rejected" || paper.ContentRevision != 2 || paperForViewer(paper, &owner)["can_revise"] != true {
		t.Fatal("再次拒绝后返修能力错误")
	}
	req := httptest.NewRequest(http.MethodPatch, fmt.Sprintf("/api/papers/%s", id), bytes.NewBufferString(`{"title":"绕过草稿"}`))
	req.Header.Set("Authorization", "Bearer "+ownerToken)
	req.Header.Set("Content-Type", "application/json")
	response := httptest.NewRecorder()
	router.ServeHTTP(response, req)
	if response.Code != 409 {
		t.Fatalf("旧接口绕过返修：%d %s", response.Code, response.Body.String())
	}
}

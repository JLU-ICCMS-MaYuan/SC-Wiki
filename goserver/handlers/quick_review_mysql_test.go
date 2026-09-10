package handlers

import (
	"bytes"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
	"strings"
	"sync"
	"testing"

	"scwiki/server/database"
	"scwiki/server/middleware"
	"scwiki/server/models"

	"github.com/gin-gonic/gin"
	"gorm.io/driver/mysql"
	"gorm.io/gorm"
	"gorm.io/gorm/logger"
)

// 真实 MySQL 审核、鉴权与历史事务；只替换事务外的发布/文件清理服务，避免污染索引。
func TestCurrentMySQLQuickReview(t *testing.T) {
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
	var calls []string
	var callsMu sync.Mutex
	service := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		callsMu.Lock()
		calls = append(calls, r.Method+" "+r.URL.Path)
		callsMu.Unlock()
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"ok":true}`))
	}))
	defer service.Close()
	t.Setenv("PYTHON_BACKEND_URL", service.URL)
	var family models.MaterialFamily
	if err := tx.First(&family).Error; err != nil {
		t.Fatal(err)
	}
	middleware.InitJWT("issue100-current-mysql-test")
	gin.SetMode(gin.TestMode)
	router := gin.New()
	router.POST("/api/admin/papers/:id/review", middleware.AuthRequired, middleware.AdminRequired, ReviewPaper)
	var paperIDs []uint
	for _, role := range []string{"admin", "superadmin"} {
		t.Run(role, func(t *testing.T) {
			var actor models.User
			if err := tx.Where("role = ? AND account_status = ?", role, "active").First(&actor).Error; err != nil {
				t.Fatal(err)
			}
			token, err := middleware.GenerateTokenForUser(actor)
			if err != nil {
				t.Fatal(err)
			}
			year := 2026
			paper := models.Paper{Title: strPtr("Issue 100 快速审核验证"), Year: &year, PaperType: strPtr("review"), SuperconductorKind: "unknown", ContentRevision: 1, ReviewStatus: "pending"}
			if err := tx.Create(&paper).Error; err != nil {
				t.Fatal(err)
			}
			paperIDs = append(paperIDs, paper.ID)
			for i, status := range []string{"approved", "pending", "rejected"} {
				body := map[string]interface{}{"status": status, "comment": "核对完成", "review_request_id": fmt.Sprintf("issue100-%d-%s", paper.ID, status)}
				if status == "approved" {
					body["superconductor_kind"] = "unknown"
					body["material_families"] = []map[string]interface{}{{"id": family.ID, "name": family.NameZH}}
					body["material_states"] = []interface{}{}
				}
				raw, _ := json.Marshal(body)
				req := httptest.NewRequest(http.MethodPost, fmt.Sprintf("/api/admin/papers/%d/review", paper.ID), bytes.NewReader(raw))
				req.Header.Set("Authorization", "Bearer "+token)
				req.Header.Set("Content-Type", "application/json")
				response := httptest.NewRecorder()
				router.ServeHTTP(response, req)
				if response.Code != 200 {
					t.Fatalf("%s 审核失败：%d %s", status, response.Code, response.Body.String())
				}
				var persisted models.Paper
				if err := tx.First(&persisted, paper.ID).Error; err != nil {
					t.Fatal(err)
				}
				if persisted.ReviewStatus != status {
					t.Fatalf("状态未保存：%s", persisted.ReviewStatus)
				}
				if (persisted.ApprovedRevision != nil) != (status == "approved") {
					t.Fatal("批准版本不匹配")
				}
				var events int64
				if err := tx.Model(&models.PaperHistoryEvent{}).Where("paper_id = ? AND event_type = ?", paper.ID, "reviewed").Count(&events).Error; err != nil || events != int64(i+1) {
					t.Fatal("审核历史缺失或重复")
				}
			}
		})
	}
	callsMu.Lock()
	publishCount := 0
	for _, call := range calls {
		if strings.HasSuffix(call, "/publish") {
			publishCount++
		}
	}
	callsMu.Unlock()
	if publishCount != 2 {
		t.Fatalf("批准发布调用次数 = %d", publishCount)
	}
	// 对用户指出的论文只读执行原 Evidence 检查，确认没有绕过第二个问题。
	var existing models.Paper
	if err := tx.First(&existing, 29).Error; err == nil {
		if err := validatePaperEvidenceComplete(tx, &existing); err == nil {
			t.Log("论文 29 的证据已完整")
		} else {
			t.Logf("论文 29 仍保留原校验：%v", err)
		}
	}
	if err := tx.Rollback().Error; err != nil {
		t.Fatal(err)
	}
	var count int64
	if err := db.Model(&models.Paper{}).Where("id IN ?", paperIDs).Count(&count).Error; err != nil || count != 0 {
		t.Fatal("测试论文未回滚")
	}
}

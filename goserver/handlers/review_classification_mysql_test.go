package handlers

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"os/exec"
	"strings"
	"testing"

	"github.com/gin-gonic/gin"
	"gorm.io/driver/mysql"
	"gorm.io/gorm"
	"scwiki/server/database"
	"scwiki/server/middleware"
	"scwiki/server/models"
)

// Python 科学保存 → Go 详情 → 实际 TS 载荷 → Go 审核 → 实际 Python prepare-review。
func TestSavedReviewClassificationsMySQL(t *testing.T) {
	base := os.Getenv("SCWIKI_CLASSIFICATION_TEST_URL")
	if base == "" {
		t.Skip("需要 #100 隔离 MySQL 与 Python 验收服务")
	}
	dsn := os.Getenv("SCWIKI_TEST_MYSQL_DSN")
	if !strings.Contains(dsn, "test") || !strings.Contains(dsn, "127.0.0.1") {
		t.Fatal("只允许隔离本地库")
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
	middleware.InitJWT(os.Getenv("JWT_SECRET_KEY"))
	gin.SetMode(gin.TestMode)
	router := gin.New()
	router.GET("/api/admin/papers/:id", middleware.AuthRequired, middleware.AdminRequired, GetPaperDetail)
	router.POST("/api/admin/papers/:id/review", middleware.AuthRequired, middleware.AdminRequired, ReviewPaper)
	// 仅发布/清理被截断，prepare-review 必须到真实 Python 服务。
	service := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path == "/api/rag/evidence/prepare-review" {
			req, _ := http.NewRequest(r.Method, base+r.URL.Path, r.Body)
			req.Header = r.Header
			resp, e := http.DefaultClient.Do(req)
			if e != nil {
				t.Error(e)
				w.WriteHeader(502)
				return
			}
			defer resp.Body.Close()
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(resp.StatusCode)
			_, _ = io.Copy(w, resp.Body)
			return
		}
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"ok":true}`))
	}))
	defer service.Close()
	t.Setenv("PYTHON_BACKEND_URL", service.URL)
	for _, role := range []string{"admin", "superadmin"} {
		t.Run(role, func(t *testing.T) {
			var actor models.User
			if err := db.Where("role = ?", role).First(&actor).Error; err != nil {
				t.Fatal(err)
			}
			token, _ := middleware.GenerateTokenForUser(actor)
			year := 2026
			title, kind := "#100 isolated "+role, "review"
			paper := models.Paper{Title: &title, Year: &year, PaperType: &kind, ContentRevision: 1, ReviewStatus: "pending", SuperconductorKind: "conventional"}
			if err := db.Create(&paper).Error; err != nil {
				t.Fatal(err)
			}
			call := func(method, path string, body any) *httptest.ResponseRecorder {
				raw, _ := json.Marshal(body)
				req := httptest.NewRequest(method, path, bytes.NewReader(raw))
				req.Header.Set("Authorization", "Bearer "+token)
				req.Header.Set("Content-Type", "application/json")
				w := httptest.NewRecorder()
				router.ServeHTTP(w, req)
				return w
			}
			remote := func(path string, body any) map[string]any {
				raw, _ := json.Marshal(body)
				method := http.MethodPut
				if strings.HasPrefix(path, "/test/") {
					method = http.MethodPost
				}
				req, _ := http.NewRequest(method, base+path, bytes.NewReader(raw))
				req.Header.Set("Authorization", "Bearer "+token)
				req.Header.Set("Content-Type", "application/json")
				resp, e := http.DefaultClient.Do(req)
				if e != nil {
					t.Fatal(e)
				}
				defer resp.Body.Close()
				data, _ := io.ReadAll(resp.Body)
				if resp.StatusCode != 200 {
					t.Fatalf("保存/确认失败 %d %s", resp.StatusCode, data)
				}
				var out map[string]any
				if err := json.Unmarshal(data, &out); err != nil {
					t.Fatal(err)
				}
				return out
			}
			families := []any{map[string]any{"name": "新材料家族 " + role, "status": "pending"}, map[string]any{"name": "第二家族 " + role, "status": "pending"}}
			state := map[string]any{"state_key": "tin", "material": "Sn", "material_name": "Tin", "element_count": 1, "material_dimensionality": "two_dimensional", "property_modules": []any{}, "structure_families": []any{map[string]any{"name": "新结构家族 " + role, "status": "pending", "is_primary": true}}}
			draft := map[string]any{"paper_type": "review", "superconductor_kind": "unconventional", "material_families": families, "material_states": []any{state}, "structure_candidates": []any{}}
			path := fmt.Sprintf("/api/rag/papers/%d/scientific-draft", paper.ID)
			remote(path, draft)
			if remote(path, draft)["data"].(map[string]any)["unchanged"] != true {
				t.Fatal("重复保存重建了数据")
			}
			getDetail := func() map[string]any {
				w := call("GET", fmt.Sprintf("/api/admin/papers/%d", paper.ID), nil)
				if w.Code != 200 {
					t.Fatal(w.Body.String())
				}
				var d map[string]any
				_ = json.Unmarshal(w.Body.Bytes(), &d)
				return d
			}
			detail := getDetail()
			if len(detail["material_families"].([]any)) != 2 {
				t.Fatal("材料家族丢失")
			}
			states := detail["material_states"].([]any)
			if len(states[0].(map[string]any)["structure_families"].([]any)) != 1 {
				t.Fatal("结构家族丢失")
			}
			input, _ := json.Marshal(map[string]any{"detail": detail, "pendingValues": map[string]any{"paper": map[string]any{"superconductor_kind": "conventional", "material_families": []any{map[string]any{"id": 999, "name": "旧家族"}}}, "material_states": []any{map[string]any{"material_dimensionality": "three_dimensional"}}}})
			cmd := exec.Command("node", "../../tests/01_decentralized_uploading/review-classification-payload.mjs")
			cmd.Stdin = bytes.NewReader(input)
			out, e := cmd.Output()
			if e != nil {
				t.Fatal(e)
			}
			var payload map[string]any
			_ = json.Unmarshal(out, &payload)
			reviewPath := fmt.Sprintf("/api/admin/papers/%d/review", paper.ID)
			if w := call("POST", reviewPath, payload); w.Code != 409 {
				t.Fatalf("未核对不应批准 %d %s", w.Code, w.Body.String())
			}
			confirmed := remote(fmt.Sprintf("/test/confirm/%d/%d", paper.ID, actor.ID), nil)
			payload["expected_evidence_version"] = confirmed["version"]
			payload["superconductor_kind"] = "conventional"
			if w := call("POST", reviewPath, payload); w.Code != 409 || !strings.Contains(w.Body.String(), "evidence_stale") {
				t.Fatalf("旧分类未拒绝 %d %s", w.Code, w.Body.String())
			}
			payload["superconductor_kind"] = "unconventional"
			for i, status := range []string{"approved", "pending", "rejected"} {
				payload["status"] = status
				payload["review_request_id"] = fmt.Sprintf("issue100-%d-%s", paper.ID, status)
				w := call("POST", reviewPath, payload)
				if w.Code != 200 {
					t.Fatalf("%s: %d %s", status, w.Code, w.Body.String())
				}
				var saved models.Paper
				db.First(&saved, paper.ID)
				if saved.ReviewStatus != status {
					t.Fatal("状态未保存")
				}
				var count int64
				db.Model(&models.PaperHistoryEvent{}).Where("paper_id = ? AND event_type = ?", paper.ID, "reviewed").Count(&count)
				if count != int64(i+1) {
					t.Fatal("历史事件数量错误")
				}
			}
		})
	}
}

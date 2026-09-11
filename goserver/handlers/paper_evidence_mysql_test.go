package handlers

import (
	"bytes"
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"strings"
	"testing"

	"github.com/gin-gonic/gin"
	"gorm.io/driver/mysql"
	"gorm.io/gorm"
	"gorm.io/gorm/logger"
	"scwiki/server/database"
	"scwiki/server/middleware"
	"scwiki/server/models"
)

// 真实 MySQL + 真实 Python 准备接口；仅事务外发布/清理在测试端承接。
func TestCurrentMySQLEvidenceReview(t *testing.T) {
	if os.Getenv("SCWIKI_CURRENT_MYSQL") != "1" || os.Getenv("SCWIKI_EVIDENCE_JOB_ID") == "" {
		t.Skip("需要现有 MySQL 与已完成的真实证据核对任务")
	}
	db, err := gorm.Open(mysql.Open(os.Getenv("SCWIKI_TEST_MYSQL_DSN")), &gorm.Config{Logger: logger.Default.LogMode(logger.Silent)})
	if err != nil {
		t.Fatal("连接当前 MySQL 失败")
	}
	sqlDB, _ := db.DB()
	defer sqlDB.Close()
	previous := database.DB
	tx := db.Begin()
	if tx.Error != nil {
		t.Fatal(tx.Error)
	}
	database.DB = tx
	defer func() { tx.Rollback(); database.DB = previous }()
	middleware.InitJWT(os.Getenv("JWT_SECRET_KEY"))
	gin.SetMode(gin.TestMode)
	var paper models.Paper
	if err := tx.First(&paper, 29).Error; err != nil {
		t.Fatal(err)
	}
	original := paper.ReviewStatus
	var actor models.User
	actorRole := os.Getenv("SCWIKI_EVIDENCE_ACTOR_ROLE")
	if actorRole == "" {
		actorRole = "superadmin"
	}
	if err := tx.Where("role = ? AND account_status = ?", actorRole, "active").First(&actor).Error; err != nil {
		t.Fatal(err)
	}
	token, err := middleware.GenerateTokenForUser(actor)
	if err != nil {
		t.Fatal(err)
	}
	var records []models.PropertyRecord
	tx.Where("paper_id = ?", 29).Order("id").Find(&records)
	values := map[uint64]string{}
	for _, r := range records {
		values[r.ID] = r.ValueRaw
	}
	var family models.MaterialFamily
	tx.First(&family)
	var states []models.MaterialState
	tx.Where("paper_id = ?", 29).Find(&states)
	classifications := []materialClassificationUpdate{}
	for _, s := range states {
		classifications = append(classifications, materialClassificationUpdate{ID: s.ID, MaterialDimensionality: "three_dimensional", StructureFamilies: []structureClassificationSelection{}})
	}
	backend := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path == "/api/rag/evidence/prepare-review" {
			req, _ := http.NewRequest(http.MethodPost, "http://127.0.0.1:8000"+r.URL.Path, r.Body)
			req.Header = r.Header.Clone()
			req.Header.Del("Accept-Encoding")
			resp, err := http.DefaultClient.Do(req)
			if err != nil {
				t.Error(err)
				w.WriteHeader(502)
				return
			}
			defer resp.Body.Close()
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(resp.StatusCode)
			io.Copy(w, resp.Body)
			return
		}
		w.Header().Set("Content-Type", "application/json")
		w.Write([]byte(`{"ok":true}`))
	}))
	defer backend.Close()
	t.Setenv("PYTHON_BACKEND_URL", backend.URL)
	router := gin.New()
	router.POST("/api/admin/papers/:id/review", middleware.AuthRequired, middleware.AdminRequired, ReviewPaper)
	router.GET("/api/admin/papers/:id/history", middleware.AuthRequired, middleware.AdminRequired, GetPaperHistory)
	router.GET("/api/papers/:id/material-states/:stateKey/export", middleware.AuthRequired, ExportMaterialState)
	base := map[string]interface{}{"status": "approved", "comment": "Issue 103 回滚验收", "review_request_id": "issue103-rollback-real-model", "evidence_job_id": os.Getenv("SCWIKI_EVIDENCE_JOB_ID"), "expected_evidence_version": os.Getenv("SCWIKI_EVIDENCE_VERSION"), "superconductor_kind": paper.SuperconductorKind, "material_families": []classificationSelection{{ID: family.ID, Name: family.NameZH}}, "material_states": classifications}
	call := func(payload map[string]interface{}, auth string) *httptest.ResponseRecorder {
		raw, _ := json.Marshal(payload)
		req := httptest.NewRequest(http.MethodPost, "/api/admin/papers/29/review", bytes.NewReader(raw))
		req.Header.Set("Authorization", "Bearer "+auth)
		req.Header.Set("Content-Type", "application/json")
		w := httptest.NewRecorder()
		router.ServeHTTP(w, req)
		return w
	}
	w := call(base, token)
	if w.Code != 409 || !strings.Contains(w.Body.String(), "evidence_review_required") {
		t.Fatalf("疑点应阻止自动批准: %d %s", w.Code, w.Body.String())
	}
	tx.First(&paper, 29)
	if paper.ReviewStatus != original {
		t.Fatal("疑点时改变了状态")
	}
	base["expected_evidence_version"] = "stale"
	w = call(base, token)
	if w.Code != 409 || !strings.Contains(w.Body.String(), "evidence_stale") {
		t.Fatalf("旧版本未拒绝: %d %s", w.Code, w.Body.String())
	}
	base["expected_evidence_version"] = os.Getenv("SCWIKI_EVIDENCE_VERSION")
	base["evidence_resolutions"] = map[string]string{"45": "回滚测试：核对原文", "46": "回滚测试：验证人工裁决留痕，不作为科学结论发布", "47": "回滚测试：验证人工裁决留痕，不作为科学结论发布"}
	w = call(base, token)
	if w.Code != 200 {
		t.Fatalf("人工裁决失败: %d %s", w.Code, w.Body.String())
	}
	if err := validatePaperEvidenceComplete(tx, &paper); err != nil {
		t.Fatal(err)
	}
	var events int64
	tx.Model(&models.PaperHistoryEvent{}).Where("operation_id = ?", base["review_request_id"]).Count(&events)
	if events != 1 {
		t.Fatal("缺少审核事件")
	}
	w = call(base, token)
	if w.Code != 200 {
		t.Fatalf("幂等重试失败: %s", w.Body.String())
	}
	tx.Model(&models.PaperHistoryEvent{}).Where("operation_id = ?", base["review_request_id"]).Count(&events)
	if events != 1 {
		t.Fatal("重复写审核事件")
	}
	for _, r := range records {
		var stored models.PropertyRecord
		tx.First(&stored, r.ID)
		if stored.ValueRaw != values[r.ID] {
			t.Fatal("核对修改了科学值")
		}
	}
	req := httptest.NewRequest(http.MethodGet, "/api/admin/papers/29/history", nil)
	req.Header.Set("Authorization", "Bearer "+token)
	history := httptest.NewRecorder()
	router.ServeHTTP(history, req)
	if history.Code != 200 || !strings.Contains(history.Body.String(), "验证人工裁决留痕") {
		t.Fatal("人工理由未在历史接口可见")
	}
	exportState := func(stateKey string) *httptest.ResponseRecorder {
		req := httptest.NewRequest(http.MethodGet, "/api/papers/29/material-states/"+stateKey+"/export", nil)
		req.Header.Set("Authorization", "Bearer "+token)
		response := httptest.NewRecorder()
		router.ServeHTTP(response, req)
		return response
	}
	for _, state := range states {
		response := exportState(state.StateKey)
		if response.Code != 200 || !strings.Contains(response.Body.String(), "evidences") {
			t.Fatalf("补证后的材料状态导出失败: %d %s", response.Code, response.Body.String())
		}
	}
	if err := tx.SavePoint("export_evidence_guard").Error; err != nil {
		t.Fatal(err)
	}
	if err := tx.Where("record_id = ?", records[0].ID).Delete(&models.PropertyRecordEvidence{}).Error; err != nil {
		t.Fatal(err)
	}
	for _, state := range states {
		if state.ID == records[0].MaterialStateID {
			response := exportState(state.StateKey)
			if response.Code != 409 || !strings.Contains(response.Body.String(), "export_incomplete") {
				t.Fatalf("导出未保留缺证据约束: %d %s", response.Code, response.Body.String())
			}
		}
	}
	if err := tx.RollbackTo("export_evidence_guard").Error; err != nil {
		t.Fatal(err)
	}
	t.Log("真实模型结果、Python 准备、Go 批准、证据/历史/幂等/导出通过；外层事务回滚")
}

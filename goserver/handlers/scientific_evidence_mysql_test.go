package handlers

import (
	"bufio"
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
	"gorm.io/gorm/logger"
	"scwiki/server/database"
	"scwiki/server/middleware"
	"scwiki/server/models"
)

// 真实 Go 审核 → Python 准备 → 当前 MySQL。模型判断固定；发布副作用不发往正式服务。
func TestCurrentMySQLScientificEvidenceTransaction(t *testing.T) {
	testCurrentMySQLScientificEvidenceTransaction(t, false)
}

func TestCurrentMySQLHumanEvidenceTransaction(t *testing.T) {
	testCurrentMySQLScientificEvidenceTransaction(t, true)
}

func testCurrentMySQLScientificEvidenceTransaction(t *testing.T, human bool) {
	if os.Getenv("SCWIKI_CURRENT_MYSQL") != "1" {
		t.Skip("需要显式选择当前 MySQL")
	}
	if human {
		t.Setenv("SCWIKI_TEST_HUMAN_CONFIRM", "1")
	}
	python := os.Getenv("SCWIKI_TEST_PYTHON")
	if python == "" {
		t.Fatal("SCWIKI_TEST_PYTHON 未设置")
	}
	bridge := exec.Command(python, "../../tests/01_decentralized_uploading/scientific_review_bridge.py")
	bridge.Env = append(os.Environ(), "PYTHONPATH=../..")
	stdout, err := bridge.StdoutPipe()
	if err != nil {
		t.Fatal(err)
	}
	bridge.Stderr = os.Stderr
	if err := bridge.Start(); err != nil {
		t.Fatal(err)
	}
	defer func() { _ = bridge.Process.Kill(); _ = bridge.Wait() }()
	scanner := bufio.NewScanner(stdout)
	if !scanner.Scan() {
		t.Fatal("Python 验收桥未启动")
	}
	baseURL := "http://127.0.0.1:" + scanner.Text()
	t.Setenv("PYTHON_BACKEND_URL", baseURL)
	db, err := gorm.Open(mysql.Open(os.Getenv("SCWIKI_TEST_MYSQL_DSN")), &gorm.Config{Logger: logger.Default.LogMode(logger.Silent)})
	if err != nil {
		t.Fatal("当前 MySQL 连接失败")
	}
	sqlDB, _ := db.DB()
	defer sqlDB.Close()
	var paper models.Paper
	// 使用分类完整的既有论文，测试重新审核；结束恢复全部原状态。
	if err := db.Where("id = ?", 9).First(&paper).Error; err != nil {
		t.Fatal(err)
	}
	var actor models.User
	if err := db.Where("role = ? AND account_status = ? AND id <> ?", "admin", "active", paper.UploadedBy).First(&actor).Error; err != nil {
		t.Fatal(err)
	}
	middleware.InitJWT(os.Getenv("JWT_SECRET_KEY"))
	token, err := middleware.GenerateTokenForUser(actor)
	if err != nil {
		t.Fatal(err)
	}
	response, err := http.Get(fmt.Sprintf("%s/snapshot/%d", baseURL, paper.ID))
	if err != nil {
		t.Fatal(err)
	}
	var snap struct {
		Version string   `json:"version"`
		Keys    []string `json:"keys"`
	}
	err = json.NewDecoder(response.Body).Decode(&snap)
	response.Body.Close()
	if err != nil {
		t.Fatal(err)
	}
	tx := db.Begin()
	previous := database.DB
	database.DB = tx
	defer func() { tx.Rollback(); database.DB = previous }()
	var families []classificationSelection
	tx.Raw("SELECT f.id,f.name_zh AS name FROM material_families f JOIN paper_material_families p ON p.material_family_id=f.id WHERE p.paper_id=?", paper.ID).Scan(&families)
	var states []models.MaterialState
	tx.Where("paper_id = ?", paper.ID).Find(&states)
	classifications := []materialClassificationUpdate{}
	for _, state := range states {
		var links []structureClassificationSelection
		tx.Raw("SELECT f.id,f.name_zh AS name,l.is_primary FROM structure_families f JOIN material_state_structure_families l ON l.structure_family_id=f.id WHERE l.material_state_id=?", state.ID).Scan(&links)
		classifications = append(classifications, materialClassificationUpdate{ID: state.ID, MaterialDimensionality: state.MaterialDimensionality, StructureFamilies: links})
	}
	// 审核 handler 的事务外发布和清理只进入本地接收器；准备请求继续走真实 Python。
	relay := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if strings.HasSuffix(r.URL.Path, "prepare-review") {
			raw, _ := io.ReadAll(r.Body)
			req, _ := http.NewRequest(http.MethodPost, baseURL+r.URL.Path, bytes.NewReader(raw))
			req.Header = r.Header.Clone()
			resp, err := http.DefaultClient.Do(req)
			if err != nil {
				t.Error(err)
				w.WriteHeader(502)
				return
			}
			defer resp.Body.Close()
			var body any
			_ = json.NewDecoder(resp.Body).Decode(&body)
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(resp.StatusCode)
			_ = json.NewEncoder(w).Encode(body)
			return
		}
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"ok":true}`))
	}))
	defer relay.Close()
	t.Setenv("PYTHON_BACKEND_URL", relay.URL)
	router := gin.New()
	router.POST("/api/admin/papers/:id/review", middleware.AuthRequired, middleware.AdminRequired, ReviewPaper)
	body := map[string]any{"status": "approved", "review_request_id": "scientific-evidence-rollback-test", "expected_evidence_version": snap.Version, "superconductor_kind": paper.SuperconductorKind, "material_families": families, "material_states": classifications}
	call := func() *httptest.ResponseRecorder {
		raw, _ := json.Marshal(body)
		r := httptest.NewRequest("POST", fmt.Sprintf("/api/admin/papers/%d/review", paper.ID), bytes.NewReader(raw))
		r.Header.Set("Authorization", "Bearer "+token)
		r.Header.Set("Content-Type", "application/json")
		w := httptest.NewRecorder()
		router.ServeHTTP(w, r)
		return w
	}
	w := call()
	expectedError := "evidence_review_required"
	if human {
		expectedError = "evidence_missing"
	}
	if w.Code != 409 || !strings.Contains(w.Body.String(), expectedError) {
		t.Fatalf("疑点应暂停：%d %s", w.Code, w.Body.String())
	}
	body["expected_evidence_version"] = "stale"
	w = call()
	if w.Code != 409 || !strings.Contains(w.Body.String(), "evidence_stale") {
		t.Fatalf("旧版本应拒绝：%d %s", w.Code, w.Body.String())
	}
	body["expected_evidence_version"] = snap.Version
	reasons := map[string]string{}
	for _, key := range snap.Keys {
		reasons[key] = "事务回滚验收：已核对原文，结果不发布"
	}
	records, err := preparePaperEvidence(tx, &paper, "Bearer "+token, "", snap.Version, reasons)
	if err != nil {
		t.Fatal(err)
	}
	if human {
		for _, record := range records {
			if !validHumanEvidence(record) || len(record.Evidences) != 0 {
				t.Fatal("人工确认应携带版本决定，不伪造引句")
			}
		}
	}
	body["evidence_resolutions"] = reasons
	w = call()
	if w.Code != 200 {
		t.Fatalf("逐条裁决应通过：%d %s", w.Code, w.Body.String())
	}
	var count int64
	tx.Table("scientific_evidence_sources").Where("paper_id = ? AND paper_revision = ?", paper.ID, paper.ContentRevision).Count(&count)
	if count != int64(len(snap.Keys)) {
		t.Fatalf("正式来源缺项：%d/%d", count, len(snap.Keys))
	}
	tx.Table("scientific_evidence_checks").Where("target = ? AND target_id = ?", "paper", fmt.Sprint(paper.ID)).Count(&count)
	if count != 0 {
		t.Fatal("临时结果未清理")
	}
	w = call()
	if w.Code != 200 {
		t.Fatalf("幂等续提失败：%s", w.Body.String())
	}
	tx.Table("paper_history_events").Where("operation_id = ?", "scientific-evidence-rollback-test").Count(&count)
	if count != 1 {
		t.Fatalf("重复审核历史：%d", count)
	}
	// 模拟证据写入后发生失败，事务必须同时恢复临时内容和正式来源。
	if err := tx.Exec(`INSERT INTO scientific_evidence_checks (target,target_id,item_key,content_hash,source_hash,rule_version,result,resolutions,actor_user_id) VALUES ('paper',?,'rollback-probe','probe','probe','probe','{}','{}',?)`, fmt.Sprint(paper.ID), actor.ID).Error; err != nil {
		t.Fatal(err)
	}
	var before int64
	tx.Table("scientific_evidence_sources").Where("paper_id = ?", paper.ID).Count(&before)
	failed := tx.Transaction(func(inner *gorm.DB) error {
		if err := applyPaperEvidence(inner, &paper, records); err != nil {
			return err
		}
		return fmt.Errorf("模拟审核历史写入失败")
	})
	if failed == nil {
		t.Fatal("应模拟事务失败")
	}
	var restored int64
	tx.Table("scientific_evidence_sources").Where("paper_id = ?", paper.ID).Count(&restored)
	if restored != before {
		t.Fatal("失败事务残留正式来源")
	}
	tx.Table("scientific_evidence_checks").Where("target = ? AND target_id = ? AND item_key = ?", "paper", fmt.Sprint(paper.ID), "rollback-probe").Count(&restored)
	if restored != 1 {
		t.Fatal("失败事务丢失待处理内容")
	}

}

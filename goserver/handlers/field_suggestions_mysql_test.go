package handlers

import (
	"encoding/json"
	"errors"
	"net/http"
	"net/http/httptest"
	"os"
	"testing"

	"gorm.io/driver/mysql"
	"gorm.io/gorm"
	"gorm.io/gorm/logger"
	"scwiki/server/models"
)

// Python 回滚用例导出的真实服务端决定，经 Go 批准门禁、MySQL 归档和重读；全部写入回滚。
func TestCurrentMySQLFieldSuggestionsContract(t *testing.T) {
	if os.Getenv("SCWIKI_CURRENT_MYSQL") != "1" || os.Getenv("SCWIKI_EVIDENCE_CONTRACT") == "" {
		t.Skip("需要显式本地 MySQL 和 Python 验收契约")
	}
	raw, err := os.ReadFile(os.Getenv("SCWIKI_EVIDENCE_CONTRACT"))
	if err != nil {
		t.Fatal(err)
	}
	var records []evidenceReviewRecord
	if err = json.Unmarshal(raw, &records); err != nil {
		t.Fatal(err)
	}
	db, err := gorm.Open(mysql.Open(os.Getenv("SCWIKI_TEST_MYSQL_DSN")), &gorm.Config{Logger: logger.Default.LogMode(logger.Silent)})
	if err != nil {
		t.Fatal("本地 MySQL 连接失败")
	}
	sqlDB, _ := db.DB()
	defer sqlDB.Close()
	tx := db.Begin()
	defer tx.Rollback()
	title, year := "109 isolated contract", 2026
	paper := models.Paper{Title: &title, Year: &year, ReviewStatus: "pending", ContentRevision: 1}
	if err = tx.Create(&paper).Error; err != nil {
		t.Fatal(err)
	}
	index := -1
	for i, r := range records {
		if r.AdoptedBasis == "general_knowledge" {
			index = i
			break
		}
	}
	if index < 0 {
		t.Fatal("缺少实际推测采用记录")
	}
	confirmed := records[index].Decision
	records[index].Decision = json.RawMessage(`{"accepted":true,"human_confirmed":false,"actor_user_id":7}`)
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Header.Get("Authorization") != "Bearer fixture" {
			t.Error("未转发身份")
		}
		_ = json.NewEncoder(w).Encode(map[string]interface{}{"records": records})
	}))
	defer server.Close()
	t.Setenv("PYTHON_BACKEND_URL", server.URL)
	if _, err = preparePaperEvidence(tx, &paper, "Bearer fixture", "", "v1", nil); err == nil {
		t.Fatal("无管理员理由的推测不得批准")
	}
	records[index].Decision = confirmed
	approved, err := preparePaperEvidence(tx, &paper, "Bearer fixture", "", "v1", nil)
	if err != nil {
		t.Fatal(err)
	}
	aborted := errors.New("验证事务失败回滚")
	err = tx.Transaction(func(inner *gorm.DB) error {
		if err := applyPaperEvidence(inner, &paper, approved); err != nil {
			return err
		}
		return aborted
	})
	if !errors.Is(err, aborted) {
		t.Fatal(err)
	}
	var count int64
	tx.Table("scientific_evidence_sources").Where("paper_id = ?", paper.ID).Count(&count)
	if count != 0 {
		t.Fatal("失败事务残留永久记录")
	}
	if err = applyPaperEvidence(tx, &paper, approved); err != nil {
		t.Fatal(err)
	}
	var stored string
	if err = tx.Table("scientific_evidence_sources").Select("result").Where("paper_id = ? AND item_key = ?", paper.ID, records[index].ItemKey).Scan(&stored).Error; err != nil {
		t.Fatal(err)
	}
	var result evidenceReviewRecord
	if err = json.Unmarshal([]byte(stored), &result); err != nil {
		t.Fatal(err)
	}
	if result.AdoptedBasis != "general_knowledge" || !validHumanEvidence(result) {
		t.Fatal("永久归档丢失推测来源或人工理由")
	}
	tx.Table("scientific_evidence_sources").Where("paper_id = ?", paper.ID).Count(&count)
	if int(count) != len(records) {
		t.Fatal("空字段和未采用建议也应保留")
	}
}

package handlers

import (
	"encoding/json"
	"fmt"
	"os"
	"strings"
	"testing"
	"time"

	driver "github.com/go-sql-driver/mysql"
	"gorm.io/driver/mysql"
	"gorm.io/gorm"
	"gorm.io/gorm/logger"
	"scwiki/server/models"
)

func TestWorkflowPrivateStatusWithLargeSnapshotsMySQL(t *testing.T) {
	dsn := os.Getenv("SCWIKI_WORKFLOW_MYSQL_DSN")
	if dsn == "" {
		t.Skip("仅显式隔离MySQL")
	}
	config, err := driver.ParseDSN(dsn)
	if err != nil {
		t.Fatal("无效的隔离DSN")
	}
	if !strings.HasPrefix(config.DBName, "scwiki_issue139_test_six_213_") || !strings.HasPrefix(config.Addr, "127.0.0.1:") {
		t.Fatal("拒绝连接非本次隔离库")
	}
	db, err := gorm.Open(mysql.Open(dsn), &gorm.Config{Logger: logger.Default.LogMode(logger.Silent)})
	if err != nil {
		t.Fatal(err)
	}
	connection, _ := db.DB()
	defer connection.Close()
	tx := db.Begin()
	if tx.Error != nil {
		t.Fatal(tx.Error)
	}
	defer tx.Rollback()
	if err := tx.Exec("SET SESSION sort_buffer_size=32768").Error; err != nil {
		t.Fatal(err)
	}
	key := fmt.Sprintf("workflow%d", time.Now().UnixNano())
	owner := models.User{Username: key, Email: key + "@isolated.invalid", PasswordHash: "isolated", RealName: "隔离验证"}
	if err := tx.Create(&owner).Error; err != nil {
		t.Fatal(err)
	}
	revision := uint(1)
	year := 2026
	public := models.Paper{Year: &year, Title: strPtr("隔离公开原稿"), UploadedBy: &owner.ID, PaperType: strPtr("review"),
		ReviewStatus: "approved", ContentRevision: 1, ApprovedRevision: &revision}
	if err := tx.Create(&public).Error; err != nil {
		t.Fatal(err)
	}
	for index, holder := range []string{"author", "review", "published", "author"} {
		status := map[string]string{"author": "rejected", "review": "pending", "published": "approved"}[holder]
		payload, _ := json.Marshal(map[string]any{"handoff": map[string]any{"contract": "manuscript-handoff-v1", "holder": holder}, "manuscript_snapshot": strings.Repeat("x", 1<<20)})
		event := models.PaperHistoryEvent{PaperID: public.ID, PaperRevision: 1, EventType: "reviewed", ReviewStatus: &status,
			ActorUserID: &owner.ID, ClassificationSnapshot: payload, OccurredAt: time.Now().Add(-time.Duration(index) * time.Minute)}
		if err := tx.Create(&event).Error; err != nil {
			t.Fatal(err)
		}
		rows, err := paperWorkflows(tx, []models.Paper{public})
		if err != nil || rows[public.ID].Status != status {
			t.Fatalf("最新处理状态错误: %v", err)
		}
		var count int64
		if err := tx.Model(&models.Paper{}).Where("papers.id = ? AND "+workflowStatusSQL(tx)+" = ?", public.ID, status).Count(&count).Error; err != nil || count != 1 {
			t.Fatalf("筛选与展示不一致: count=%d err=%v", count, err)
		}
		var reread models.Paper
		if err := tx.First(&reread, public.ID).Error; err != nil {
			t.Fatal(err)
		}
		if reread.ReviewStatus != "approved" || *reread.Title != "隔离公开原稿" {
			t.Fatal("处理状态改变公开内容")
		}
	}
}

package handlers

import (
	"crypto/sha256"
	"fmt"
	"net/http"
	"os"
	"testing"

	"github.com/gin-gonic/gin"
	"scwiki/server/models"
)

// 真实列表处理器与隔离SQLite；所有条目均早于周一，验证空周不再隐藏已有内容。
func TestNewsAllDatesBrowserPreview(t *testing.T) {
	address := os.Getenv("NEWS_ALL_DATES_PREVIEW_ADDRESS")
	if address == "" {
		t.Skip("未启用全日期资讯隔离预览")
	}
	db := newsTestDB(t)
	if err := db.Exec("INSERT INTO material_families VALUES (1, '氢基超导体', 'Hydrides')").Error; err != nil {
		t.Fatal(err)
	}
	dates := []string{"2026-11-01T00:00:00Z", "2026-10-31T00:00:00Z", "2026-10-30T00:00:00Z", "2026-10-15T00:00:00Z", "2026-10-01T00:00:00Z", "2025-01-01T00:00:00Z", ""}
	for _, kind := range []string{"news", "preprint", "journal_article"} {
		for index, published := range dates {
			precision := "day"
			if index == 4 {
				precision = "month"
			}
			if index == 5 {
				precision = "year"
			}
			if index == 6 {
				precision = "unknown"
			}
			row := models.NewsFeedItem{ID: fmt.Sprintf("%s-%d", kind, index), Kind: kind, DisplayKind: kind, Source: "arxiv", Title: fmt.Sprintf("%s fixture %d", kind, index), URL: "https://example.org/article", PublishedAt: published, DatePrecision: precision, Authors: "[]", Links: "[]"}
			if err := db.Create(&row).Error; err != nil {
				t.Fatal(err)
			}
			paperType, subtype := "theoretical", "calculation"
			classification := models.NewsFeedClassification{ItemID: row.ID, PaperType: &paperType, TheoreticalSubtype: &subtype, Status: "completed", ContentHash: fmt.Sprintf("%x", sha256.Sum256([]byte(row.Title+"\x00")))}
			if err := db.Create(&classification).Error; err != nil {
				t.Fatal(err)
			}
			if err := db.Create(&models.NewsFeedMaterialFamily{ItemID: row.ID, MaterialFamilyID: 1}).Error; err != nil {
				t.Fatal(err)
			}
		}
	}
	router := gin.New()
	router.GET("/api/news/feed", ListNewsFeed)
	t.Fatal(http.ListenAndServe(address, router))
}

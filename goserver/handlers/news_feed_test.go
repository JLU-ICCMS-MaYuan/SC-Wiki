package handlers

import (
	"crypto/sha256"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
	"strings"
	"testing"
	"time"

	"github.com/gin-gonic/gin"
	"gorm.io/driver/mysql"
	"gorm.io/driver/sqlite"
	"gorm.io/gorm"
	"scwiki/server/database"
	"scwiki/server/models"
)

func newsTestDB(t *testing.T) *gorm.DB {
	t.Helper()
	db, err := gorm.Open(sqlite.Open(":memory:"), &gorm.Config{})
	if err != nil {
		t.Fatal(err)
	}
	sqlDB, _ := db.DB()
	sqlDB.SetMaxOpenConns(1)
	old := database.DB
	database.DB = db
	t.Cleanup(func() { database.DB = old; sqlDB.Close() })
	if err := db.AutoMigrate(&models.NewsFeedItem{}, &models.NewsFeedSource{}, &models.NewsItem{}, &models.NewsFeedClassification{}, &models.NewsFeedMaterialFamily{}); err != nil {
		t.Fatal(err)
	}
	if err := db.Exec("CREATE TABLE material_families (id INTEGER PRIMARY KEY, name_zh TEXT, name_en TEXT)").Error; err != nil {
		t.Fatal(err)
	}
	return db
}

func TestNewsClassificationCurrentAndStaleResults(t *testing.T) {
	db := newsTestDB(t)
	if err := db.Exec("INSERT INTO material_families VALUES (1, '氢基超导体', 'Hydrides')").Error; err != nil {
		t.Fatal(err)
	}
	kind, subtype := "theoretical", "theory"
	for _, id := range []string{"current", "stale", "failed", "pending"} {
		item := models.NewsFeedItem{ID: id, Kind: "preprint", Title: "中文标题 <test>", Summary: "摘要", Authors: "[]", Links: "[]"}
		if err := db.Create(&item).Error; err != nil {
			t.Fatal(err)
		}
		if id == "pending" {
			continue
		}
		result := models.NewsFeedClassification{ItemID: id, PaperType: &kind, TheoreticalSubtype: &subtype,
			ContentHash: fmt.Sprintf("%x", sha256.Sum256([]byte(item.Title+"\x00"+item.Summary))), Status: "completed"}
		if id == "stale" {
			result.ContentHash = "old"
		}
		if id == "failed" {
			result.Status = "failed"
		}
		if err := db.Create(&result).Error; err != nil {
			t.Fatal(err)
		}
		if err := db.Create(&models.NewsFeedMaterialFamily{ItemID: id, MaterialFamilyID: 1}).Error; err != nil {
			t.Fatal(err)
		}
	}
	response := newsRequest("/api/news/feed")
	if response.Code != 200 {
		t.Fatalf("%d %s", response.Code, response.Body.String())
	}
	var body struct{ Items []newsFeedView }
	if err := json.Unmarshal(response.Body.Bytes(), &body); err != nil {
		t.Fatal(err)
	}
	for _, item := range body.Items {
		if item.ID == "current" {
			if item.PaperType == nil || *item.PaperType != kind || item.TheoreticalSubtype == nil || *item.TheoreticalSubtype != subtype || len(item.MaterialFamilies) != 1 || item.MaterialFamilies[0].NameZh != "氢基超导体" {
				t.Fatalf("missing classification: %+v", item)
			}
		} else if item.PaperType != nil || item.TheoreticalSubtype != nil || item.MaterialFamilies == nil || len(item.MaterialFamilies) != 0 {
			t.Fatalf("stale or unavailable classification must be empty: %+v", item)
		}
	}
}

func newsRequest(path string) *httptest.ResponseRecorder {
	gin.SetMode(gin.TestMode)
	router := gin.New()
	router.GET("/api/news/feed", ListNewsFeed)
	router.GET("/api/news", ListNews)
	result := httptest.NewRecorder()
	router.ServeHTTP(result, httptest.NewRequest(http.MethodGet, path, nil))
	return result
}

func TestNewsFeedPaginationAndKinds(t *testing.T) {
	db := newsTestDB(t)
	for _, item := range []models.NewsFeedItem{
		{ID: "a", Kind: "preprint", Title: "Older", PublishedAt: "2026-08-29T00:00:00Z", Authors: "[]", Links: "[]"},
		{ID: "b", Kind: "preprint", Title: "Newer", PublishedAt: "2026-08-30T00:00:00Z", Authors: "[]", Links: "[]"},
		{ID: "c", Kind: "news", Title: "News", PublishedAt: "2026-08-31T00:00:00Z", Authors: "[]", Links: "[]"},
	} {
		if err := db.Create(&item).Error; err != nil {
			t.Fatal(err)
		}
	}
	response := newsRequest("/api/news/feed?kind=preprint&page=2&page_size=1")
	if response.Code != 200 {
		t.Fatalf("%d %s", response.Code, response.Body.String())
	}
	var body struct {
		Items []struct {
			ID      string
			Notice  string
			Authors []string
		}
		Total   int
		Sources []struct {
			Source string
			Status string
		}
	}
	if err := json.Unmarshal(response.Body.Bytes(), &body); err != nil {
		t.Fatal(err)
	}
	if body.Total != 2 || len(body.Items) != 1 || body.Items[0].ID != "a" {
		t.Fatalf("%+v", body)
	}
	if body.Items[0].Notice != "自动采集，未经本站审核" || len(body.Sources) != 13 || body.Sources[0].Status != "never" {
		t.Fatalf("%+v", body)
	}
}

func TestNewsFeedAllDatesAndStablePagination(t *testing.T) {
	db := newsTestDB(t)
	for _, item := range []models.NewsFeedItem{
		{ID: "new", PublishedAt: "2026-11-02T00:00:00Z", DatePrecision: "day", FirstSeenAt: "2026-11-02T01:00:00Z"},
		{ID: "sunday-a", PublishedAt: "2026-11-01T00:00:00Z", DatePrecision: "day", FirstSeenAt: "2026-11-02T00:02:06Z"},
		{ID: "sunday-b", PublishedAt: "2026-11-01T00:00:00Z", DatePrecision: "day", FirstSeenAt: "2026-11-02T00:02:06Z"},
		{ID: "older", PublishedAt: "2026-10-30T00:00:00Z", DatePrecision: "day", FirstSeenAt: "2026-11-03T00:00:00Z"},
		{ID: "month", PublishedAt: "2026-10-01T00:00:00Z", DatePrecision: "month"},
		{ID: "year", PublishedAt: "2025-01-01T00:00:00Z", DatePrecision: "year"},
		{ID: "unknown", PublishedAt: "", DatePrecision: "unknown"},
	} {
		item.Kind, item.Authors, item.Links = "preprint", "[]", "[]"
		if err := db.Create(&item).Error; err != nil {
			t.Fatal(err)
		}
	}
	want := [][]string{{"new", "sunday-b"}, {"sunday-a", "older"}, {"month", "year"}, {"unknown"}}
	for page, ids := range want {
		// 无日期参数与旧缓存客户端的日期参数都必须读取同一连续列表。
		for _, legacy := range []string{"", "&period=week&week=2026-11-02", "&period=history&week=invalid"} {
			response := newsRequest(fmt.Sprintf("/api/news/feed?kind=preprint&page_size=2&page=%d%s", page+1, legacy))
			if response.Code != 200 {
				t.Fatal(response.Body.String())
			}
			var result struct {
				Items []newsFeedView
				Total int
			}
			if err := json.Unmarshal(response.Body.Bytes(), &result); err != nil {
				t.Fatal(err)
			}
			if result.Total != 7 || len(result.Items) != len(ids) {
				t.Fatalf("%+v", result)
			}
			for i, id := range ids {
				if result.Items[i].ID != id {
					t.Fatalf("page %d: %+v", page+1, result.Items)
				}
				if id == "month" && result.Items[i].DatePrecision != "month" {
					t.Fatal("日期精度丢失")
				}
			}
			var fields map[string]json.RawMessage
			if err := json.Unmarshal(response.Body.Bytes(), &fields); err != nil {
				t.Fatal(err)
			}
			for _, field := range []string{"week", "week_end", "period", "timezone"} {
				if _, ok := fields[field]; ok {
					t.Fatalf("退役字段仍存在: %s", field)
				}
			}
		}
	}
}

func TestNewsContentSemanticsOverrideLegacyColumn(t *testing.T) {
	db := newsTestDB(t)
	for _, row := range []models.NewsFeedItem{
		{ID: "report", Kind: "news", Source: "physorg", ContentType: "research_report", DisplayKind: "journal_article"},
		{ID: "publisher-news", Kind: "journal_article", Source: "crossref", DOI: "10.1038/d41586-026-00001", ContentType: "peer_reviewed"},
		{ID: "science-news", Kind: "journal_article", Source: "science", URL: "http://www.science.org/content/article/report"},
		{ID: "aps-news", Kind: "journal_article", Source: "crossref", DOI: "10.1103/physics.19.1"},
		{ID: "acs-news", Kind: "journal_article", Source: "crossref", DOI: "10.1021/cen-v100n001.p01"},
		{ID: "journal", Kind: "journal_article", Source: "aps", ContentType: "journal_article"},
		{ID: "preprint", Kind: "preprint", Source: "arxiv", DisplayKind: "journal_article"},
	} {
		row.Authors, row.Links = "[]", "[]"
		if err := db.Create(&row).Error; err != nil {
			t.Fatal(err)
		}
	}
	for kind, count := range map[string]int{"news": 5, "preprint": 1, "journal_article": 1} {
		w := newsRequest("/api/news/feed?kind=" + kind)
		var body struct {
			Items []newsFeedView
			Total int
		}
		if w.Code != 200 || json.Unmarshal(w.Body.Bytes(), &body) != nil {
			t.Fatal(w.Body.String())
		}
		if body.Total != count || len(body.Items) != count {
			t.Fatalf("%s: %+v", kind, body)
		}
		for _, item := range body.Items {
			if item.Kind != kind || item.DisplayKind != kind {
				t.Fatalf("query and item semantics differ: %+v", item)
			}
			if kind == "news" && item.ContentType != "research_report" {
				t.Fatal(item.ContentType)
			}
		}
	}
	var original models.NewsFeedItem
	if err := db.First(&original, "id = ?", "report").Error; err != nil {
		t.Fatal(err)
	}
	if original.DisplayKind != "journal_article" {
		t.Fatal("read must not rewrite stored provenance")
	}
}

func TestNewsSemanticsBrowserPreview(t *testing.T) {
	address := os.Getenv("NEWS_SEMANTICS_PREVIEW_ADDRESS")
	if address == "" {
		t.Skip("未启用隔离 SQLite 资讯预览")
	}
	db := newsTestDB(t)
	url := "https://phys.org/news/2026-10-hidden-rivalry-quantum-states-heart.html"
	links, _ := json.Marshal([]map[string]string{{"source": "physorg", "url": url, "role": "discovery"}, {"source": "physorg", "url": url, "role": "original"}})
	for _, row := range []models.NewsFeedItem{
		{ID: "report", Kind: "news", DisplayKind: "journal_article", ContentType: "research_report", Source: "physorg", OriginalSource: "physorg", Title: "A hidden rivalry between two quantum states at the heart of superconductors", URL: url, Links: string(links)},
		{ID: "journal", Kind: "journal_article", ContentType: "peer_reviewed", Source: "aps", Title: "Journal fixture: superconductivity research", URL: "https://example.org/journal", Links: "[]"},
		{ID: "preprint", Kind: "preprint", Source: "arxiv", Title: "Preprint fixture: superconductivity research", URL: "https://arxiv.org/abs/2608.12345", Links: "[]"},
	} {
		row.PublishedAt, row.DatePrecision, row.Authors = time.Now().UTC().Format(time.RFC3339), "day", "[]"
		if err := db.Create(&row).Error; err != nil {
			t.Fatal(err)
		}
	}
	router := gin.New()
	router.GET("/api/news/feed", ListNewsFeed)
	t.Fatal(http.ListenAndServe(address, router))
}

func TestNewsFeedBadParametersAndDatabaseErrors(t *testing.T) {
	db := newsTestDB(t)
	for _, query := range []string{"?page=0", "?page=-1", "?page=wat", "?page=10001", "?page_size=101", "?kind=all"} {
		if response := newsRequest("/api/news/feed" + query); response.Code != 400 {
			t.Fatalf("%s: %d", query, response.Code)
		}
	}
	if response := newsRequest("/api/news"); response.Code != 200 || response.Body.String() != "[]" {
		t.Fatalf("%d %s", response.Code, response.Body.String())
	}
	sqlDB, _ := db.DB()
	sqlDB.Close()
	for _, path := range []string{"/api/news/feed", "/api/news"} {
		response := newsRequest(path)
		if response.Code != 500 {
			t.Fatalf("%s: %d", path, response.Code)
		}
	}
}

// 可选：读取同一隔离 MySQL，验证 Python 写入与 Go 读取的真实契约。
func TestNewsFeedMySQLContract(t *testing.T) {
	dsn := os.Getenv("NEWS_TEST_MYSQL_DSN")
	if dsn == "" {
		t.Skip("需要显式测试 MySQL DSN")
	}
	db, err := gorm.Open(mysql.Open(dsn), &gorm.Config{})
	if err != nil {
		t.Fatal(err)
	}
	old := database.DB
	database.DB = db
	sqlDB, _ := db.DB()
	t.Cleanup(func() { database.DB = old; sqlDB.Close() })
	response := newsRequest("/api/news/feed")
	if response.Code != 200 {
		t.Fatalf("%d %s", response.Code, response.Body.String())
	}
	var result struct {
		Items []newsFeedView
		Total int
	}
	if err := json.Unmarshal(response.Body.Bytes(), &result); err != nil {
		t.Fatal(err)
	}
	if result.Total < 1 || len(result.Items) == 0 {
		t.Fatal("未读到 Python 写入的资讯")
	}
	for _, item := range result.Items {
		if item.Notice == "" || item.URL == "" {
			t.Fatalf("契约缺字段: %+v", item)
		}
		if os.Getenv("NEWS_TEST_REQUIRE_CLASSIFICATION") == "1" && (item.PaperType == nil || *item.PaperType != "theoretical" || item.TheoreticalSubtype == nil || *item.TheoreticalSubtype != "calculation" || len(item.MaterialFamilies) != 1 || item.MaterialFamilies[0].NameZh != "氢基超导体") {
			t.Fatalf("Python 分类未正确传递: %+v", item)
		}
	}
}

func TestNewsFeedCandidatePrivacyMySQL(t *testing.T) {
	dsn := os.Getenv("NEWS_TEST_MYSQL_DSN")
	if dsn == "" {
		t.Skip("需要显式隔离 MySQL")
	}
	db, err := gorm.Open(mysql.Open(dsn), &gorm.Config{})
	if err != nil {
		t.Fatal(err)
	}
	old := database.DB
	database.DB = db
	sqlDB, _ := db.DB()
	t.Cleanup(func() { database.DB = old; sqlDB.Close() })
	for _, period := range []string{"all", "week", "history"} {
		router := gin.New()
		router.GET("/api/news/feed", ListNewsFeed)
		response := httptest.NewRecorder()
		router.ServeHTTP(response, httptest.NewRequest(http.MethodGet, "/api/news/feed?kind=journal_article&period="+period+"&week=2026-11-02", nil))
		if response.Code != 200 {
			t.Fatalf("%d %s", response.Code, response.Body.String())
		}
		var result struct {
			Items []newsFeedView
			Total int
		}
		if err := json.Unmarshal(response.Body.Bytes(), &result); err != nil {
			t.Fatal(err)
		}
		want := 1
		if result.Total != want || len(result.Items) != want {
			t.Fatalf("候选不应进入公开计数: %s %+v", period, result)
		}
		if want == 1 && (result.Items[0].DOI != "10.1002/relevance0" || result.Items[0].Summary != "") {
			t.Fatalf("公开记录或摘要边界错误: %+v", result.Items)
		}
		if strings.Contains(response.Body.String(), "screening_abstract") || strings.Contains(response.Body.String(), "内部筛选摘要") {
			t.Fatal("候选私有输入泄露到API")
		}
	}
}

// 仅供本地浏览器验证。生产路由有分支既有编译问题时，不伪称已验证完整服务。
func TestNewsFeedBrowserPreview(t *testing.T) {
	address := os.Getenv("NEWS_TEST_PREVIEW_ADDRESS")
	if address == "" {
		t.Skip("未启用临时预览")
	}
	dsn := os.Getenv("NEWS_TEST_MYSQL_DSN")
	if dsn == "" {
		t.Fatal("预览只允许显式测试数据库")
	}
	db, err := gorm.Open(mysql.Open(dsn), &gorm.Config{})
	if err != nil {
		t.Fatal(err)
	}
	database.DB = db
	router := gin.New()
	router.GET("/api/news/feed", ListNewsFeed)
	router.GET("/api/news", func(c *gin.Context) {
		c.JSON(200, []models.NewsItem{{ID: 1, Title: "人工快讯（隔离测试样本）", EventDate: "2026-08-31", Summary: "用于检查人工快讯与自动资讯并存，不写入业务数据库。"}})
	})
	router.Static("/assets", "/preview/assets")
	router.GET("/news", func(c *gin.Context) { c.File("/preview/index.html") })
	t.Fatal(http.ListenAndServe(address, router))
}

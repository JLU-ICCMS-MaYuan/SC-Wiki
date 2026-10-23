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

func TestNewsNaturalWeekAndHistoryPartition(t *testing.T) {
	db := newsTestDB(t)
	for _, item := range []models.NewsFeedItem{
		{ID: "before", PublishedAt: "2026-10-18T15:59:59Z", DatePrecision: "day"},
		{ID: "start", PublishedAt: "2026-10-18T16:00:00Z", DatePrecision: "day"},
		{ID: "middle", PublishedAt: "2026-10-21T00:00:00Z", DatePrecision: "day"},
		{ID: "end", PublishedAt: "2026-10-25T15:59:59Z", DatePrecision: "day"},
		{ID: "next", PublishedAt: "2026-10-25T16:00:00Z", DatePrecision: "day"},
		{ID: "month", PublishedAt: "2026-10-21T00:00:00Z", DatePrecision: "month"},
		{ID: "unknown", PublishedAt: "", DatePrecision: "unknown"},
	} {
		item.Kind, item.Authors, item.Links = "preprint", "[]", "[]"
		if err := db.Create(&item).Error; err != nil {
			t.Fatal(err)
		}
	}
	request := func(query string, now string) *httptest.ResponseRecorder {
		n, err := time.Parse(time.RFC3339, now)
		if err != nil {
			t.Fatal(err)
		}
		r := gin.New()
		r.GET("/api/news/feed", func(c *gin.Context) { listNewsFeedAt(c, n) })
		w := httptest.NewRecorder()
		r.ServeHTTP(w, httptest.NewRequest("GET", "/api/news/feed?kind=preprint&"+query, nil))
		return w
	}
	for _, tc := range []struct {
		query string
		total int
		ids   []string
	}{
		{"period=week&page_size=2", 3, []string{"end", "middle"}},
		{"period=week&page_size=2&page=2", 3, []string{"start"}},
		{"period=history", 4, []string{"next", "month", "before", "unknown"}},
	} {
		w := request(tc.query, "2026-10-23T00:00:00Z")
		var got struct {
			Items []newsFeedView
			Total int
			Week  string
		}
		if w.Code != 200 || json.Unmarshal(w.Body.Bytes(), &got) != nil {
			t.Fatal(w.Body.String())
		}
		if got.Total != tc.total || got.Week != "2026-10-19" || len(got.Items) != len(tc.ids) {
			t.Fatalf("%s: %+v", tc.query, got)
		}
		for i, id := range tc.ids {
			if got.Items[i].ID != id {
				t.Fatalf("%s: %s != %s", tc.query, got.Items[i].ID, id)
			}
		}
	}
	// 跨周继续翻页时保留原周锚点，不把前一周页码套在新周数据上。
	w := request("period=week&week=2026-10-19&page_size=2&page=2", "2026-10-26T00:00:00Z")
	if w.Code != 200 || !strings.Contains(w.Body.String(), `"id":"start"`) {
		t.Fatal(w.Body.String())
	}
	for _, query := range []string{"period=invalid", "week=2026-10-20", "week=2026-11-02", "week=bad"} {
		if w := request(query, "2026-10-23T00:00:00Z"); w.Code != 400 {
			t.Fatalf("%s: %d", query, w.Code)
		}
	}
}

func TestNewsWeekYearBoundary(t *testing.T) {
	now, _ := time.Parse(time.RFC3339, "2026-12-31T23:00:00Z")
	start, end, err := newsWeek(now, "")
	if err != nil || start.Format("2006-01-02") != "2026-12-28" || end.Format("2006-01-02") != "2027-01-04" {
		t.Fatal(start, end, err)
	}
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

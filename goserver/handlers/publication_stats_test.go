package handlers

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"reflect"
	"strings"
	"testing"
	"time"

	"scwiki/server/cache"
	"scwiki/server/database"

	"github.com/alicebob/miniredis/v2"
	"github.com/gin-gonic/gin"
	"gorm.io/driver/mysql"
	"gorm.io/driver/sqlite"
	"gorm.io/gorm"
)

func publicationTestDB(t *testing.T) *gorm.DB {
	t.Helper()
	var driver gorm.Dialector = sqlite.Open(":memory:")
	if dsn := os.Getenv("PUBLICATION_STATS_TEST_DSN"); dsn != "" {
		if !strings.Contains(dsn, "/scwiki_publication_stats_test?") {
			t.Fatal("只允许连接隔离的 scwiki_publication_stats_test 数据库")
		}
		driver = mysql.Open(dsn)
	}
	db, err := gorm.Open(driver, &gorm.Config{})
	if err != nil {
		t.Fatal(err)
	}
	sqlDB, err := db.DB()
	if err != nil {
		t.Fatal(err)
	}
	sqlDB.SetMaxOpenConns(1)
	previous := database.DB
	database.DB = db
	t.Cleanup(func() { database.DB = previous; sqlDB.Close() })
	for _, statement := range []string{
		`CREATE TABLE papers (id INTEGER PRIMARY KEY, year INTEGER, review_status TEXT, content_revision INTEGER)`,
		`CREATE TABLE material_families (id INTEGER PRIMARY KEY, name_zh TEXT, name_en TEXT)`,
		`CREATE TABLE paper_material_families (paper_id INTEGER, paper_revision INTEGER, material_family_id INTEGER, PRIMARY KEY(paper_id,paper_revision,material_family_id))`,
	} {
		if err := db.Exec(statement).Error; err != nil {
			t.Fatal(err)
		}
	}
	t.Cleanup(func() {
		// 仅清理专用测试库；MySQL UNION 不能重复打开同一临时表。
		for _, table := range []string{"paper_material_families", "material_families", "papers"} {
			db.Exec("DROP TABLE IF EXISTS " + table)
		}
	})
	return db
}

// 显式启用的浏览器夹具：真实生产聚合接口和构建后的 SPA，共享隔离数据库。
func TestPublicationBrowserFixture(t *testing.T) {
	if os.Getenv("PUBLICATION_BROWSER_FIXTURE") != "1" {
		t.Skip("浏览器夹具未启用")
	}
	db := publicationTestDB(t)
	seedPublicationStats(t, db)
	redisServer := miniredis.RunT(t)
	cache.Connect(redisServer.Addr())
	gin.SetMode(gin.TestMode)
	router := gin.New()
	router.GET("/api/community/publication-stats", CommunityPublicationStats)
	router.GET("/api/community/contributions", func(c *gin.Context) {
		c.JSON(200, gin.H{"participant_count": 0, "upload_leaderboard": []any{}, "review_leaderboard": []any{}, "generated_at": time.Now().UTC()})
	})
	router.GET("/api/classification-catalogs", func(c *gin.Context) {
		c.JSON(200, gin.H{"material_families": []any{}, "structure_families": []any{}})
	})
	static, err := filepath.Abs("../../frontend/static")
	if err != nil {
		t.Fatal(err)
	}
	router.Static("/assets", filepath.Join(static, "assets"))
	router.NoRoute(func(c *gin.Context) {
		if strings.HasPrefix(c.Request.URL.Path, "/api/") {
			c.JSON(404, gin.H{"error": "夹具未提供此接口"})
			return
		}
		c.File(filepath.Join(static, "index.html"))
	})
	server := &http.Server{Addr: "127.0.0.1:19115", Handler: router, ReadHeaderTimeout: 5 * time.Second}
	t.Cleanup(func() { server.Close() })
	go func() {
		if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			t.Error(err)
		}
	}()
	t.Log("浏览器验收：http://127.0.0.1:19115/share/rankings；仅隔离测试数据")
	stopFile := os.Getenv("PUBLICATION_BROWSER_STOP_FILE")
	if stopFile == "" {
		t.Fatal("缺少浏览器夹具停止文件路径")
	}
	deadline := time.After(15 * time.Minute)
	ticker := time.NewTicker(time.Second)
	defer ticker.Stop()
	for {
		select {
		case <-deadline:
			t.Fatal("浏览器夹具超时")
		case <-ticker.C:
			if _, err := os.Stat(stopFile); err == nil {
				return
			}
		}
	}
}

func seedPublicationStats(t *testing.T, db *gorm.DB) {
	t.Helper()
	for _, statement := range []string{
		`INSERT INTO material_families VALUES (1,'铜基','Cuprate'),(2,'铁基','Iron-based'),(3,'零篇家族',NULL),(4,'年份未知家族','')`,
		`INSERT INTO papers VALUES (1,2020,'approved',1),(2,2022,'approved',1),(3,NULL,'approved',1),(4,2020,'pending',1),(5,2022,'rejected',1),(6,2021,'approved',2),(7,2024,'approved',2),(8,0,'approved',1),(9,10000,'approved',1),(10,-1,'approved',1),(11,2020,'approved',1)`,
		`INSERT INTO paper_material_families VALUES (1,1,1),(1,1,2),(2,1,1),(3,1,1),(4,1,1),(5,1,2),(6,1,1),(7,1,1),(7,2,2),(8,1,4),(9,1,4),(10,1,4),(11,1,1)`,
	} {
		if err := db.Exec(statement).Error; err != nil {
			t.Fatal(err)
		}
	}
}

func assertPublicationCounts(t *testing.T, snapshot publicationSnapshot) {
	t.Helper()
	ids := []uint{}
	for _, family := range snapshot.Families {
		ids = append(ids, family.FamilyID)
		total := family.UnknownYearCount
		for i, year := range family.Years {
			total += year.PaperCount
			if i > 0 && year.Year != family.Years[i-1].Year+1 {
				t.Fatal("年度未连续升序补零")
			}
		}
		if total != family.PaperCount || family.Years == nil {
			t.Fatalf("计数不守恒或数组为 null: %+v", family)
		}
	}
	if !reflect.DeepEqual(ids, []uint{1, 4, 2, 0, 3}) {
		t.Fatalf("目录遗漏或排序错误: %v", ids)
	}
	cu := snapshot.Families[0]
	if cu.PaperCount != 4 || cu.UnknownYearCount != 1 || !reflect.DeepEqual(cu.Years, []publicationYear{{2020, 2}, {2021, 0}, {2022, 1}}) {
		t.Fatalf("铜基统计错误（去重/多家族/版本/年份）: %+v", cu)
	}
	if snapshot.Families[1].UnknownYearCount != 3 || len(snapshot.Families[1].Years) != 0 {
		t.Fatal("非法年份应全归入未知")
	}
	if snapshot.Families[2].PaperCount != 2 || snapshot.Families[3].PaperCount != 1 || snapshot.Families[4].PaperCount != 0 {
		t.Fatalf("边界计数错误: %+v", snapshot)
	}
	if snapshot.GeneratedAt.IsZero() {
		t.Fatal("缺少快照时间")
	}
}

func TestPublicationAggregation(t *testing.T) {
	db := publicationTestDB(t)
	seedPublicationStats(t, db)
	// 刻意不建立材料状态或物性表，验证无 Tc 的论文仍能完整统计。
	snapshot, err := loadPublicationSnapshot(db)
	if err != nil {
		t.Fatal(err)
	}
	assertPublicationCounts(t, snapshot)
}

func TestPublicationEmptyAndStableTies(t *testing.T) {
	db := publicationTestDB(t)
	if err := db.Exec(`INSERT INTO material_families VALUES (9,'自建家族',''),(2,'零篇','')`).Error; err != nil {
		t.Fatal(err)
	}
	snapshot, err := loadPublicationSnapshot(db)
	if err != nil {
		t.Fatal(err)
	}
	if len(snapshot.Families) != 3 {
		t.Fatalf("零篇目录丢失: %+v", snapshot)
	}
	for i, id := range []uint{0, 2, 9} {
		family := snapshot.Families[i]
		if family.FamilyID != id || family.PaperCount != 0 || family.UnknownYearCount != 0 || len(family.Years) != 0 {
			t.Fatalf("空数据错误: %+v", family)
		}
	}
	if err := db.Exec(`DELETE FROM material_families`).Error; err != nil {
		t.Fatal(err)
	}
	snapshot, err = loadPublicationSnapshot(db)
	if err != nil || len(snapshot.Families) != 1 || snapshot.Families[0].FamilyID != 0 {
		t.Fatalf("全空数据库: %+v, %v", snapshot, err)
	}
}

func publicationRequest(query string) *httptest.ResponseRecorder {
	gin.SetMode(gin.TestMode)
	router := gin.New()
	router.GET("/api/community/publication-stats", CommunityPublicationStats)
	response := httptest.NewRecorder()
	router.ServeHTTP(response, httptest.NewRequest(http.MethodGet, "/api/community/publication-stats"+query, nil))
	return response
}

func TestPublicationHTTPCacheRefreshTTLAndFailure(t *testing.T) {
	db := publicationTestDB(t)
	seedPublicationStats(t, db)
	redisServer := miniredis.RunT(t)
	cache.Connect(redisServer.Addr())
	first := publicationRequest("")
	if first.Code != http.StatusOK {
		t.Fatal(first.Body.String())
	}
	var snapshot publicationSnapshot
	if err := json.Unmarshal(first.Body.Bytes(), &snapshot); err != nil {
		t.Fatal(err)
	}
	assertPublicationCounts(t, snapshot)
	if redisServer.TTL(publicationCacheKey) != time.Hour {
		t.Fatal("缓存不是一小时")
	}
	if err := db.Exec(`UPDATE papers SET review_status='pending' WHERE id=1`).Error; err != nil {
		t.Fatal(err)
	}
	if cached := publicationRequest("?refresh=false"); cached.Body.String() != first.Body.String() {
		t.Fatal("未命中公共快照")
	}
	forced := publicationRequest("?refresh=true")
	if forced.Code != http.StatusOK {
		t.Fatal(forced.Body.String())
	}
	if err := json.Unmarshal(forced.Body.Bytes(), &snapshot); err != nil {
		t.Fatal(err)
	}
	for _, f := range snapshot.Families {
		if f.FamilyID == 1 && f.PaperCount != 3 {
			t.Fatal("强制刷新未更新")
		}
	}
	if err := db.Exec(`UPDATE papers SET review_status='approved' WHERE id=1`).Error; err != nil {
		t.Fatal(err)
	}
	redisServer.FastForward(time.Hour + time.Second)
	if refreshed := publicationRequest(""); refreshed.Code != http.StatusOK {
		t.Fatal(refreshed.Body.String())
	} else {
		if err := json.Unmarshal(refreshed.Body.Bytes(), &snapshot); err != nil {
			t.Fatal(err)
		}
		assertPublicationCounts(t, snapshot)
	}
	if bad := publicationRequest("?refresh=1"); bad.Code != http.StatusBadRequest {
		t.Fatalf("非法参数: %d", bad.Code)
	}
	if err := db.Exec(`DROP TABLE papers`).Error; err != nil {
		t.Fatal(err)
	}
	if failed := publicationRequest("?refresh=true"); failed.Code != http.StatusInternalServerError {
		t.Fatalf("数据库失败未报告: %d", failed.Code)
	}
	if cached := publicationRequest(""); cached.Code != http.StatusOK {
		t.Fatal("失败覆盖了已有完整缓存")
	}
}

func TestPublicationRedisUnavailable(t *testing.T) {
	db := publicationTestDB(t)
	seedPublicationStats(t, db)
	redisServer := miniredis.RunT(t)
	cache.Connect(redisServer.Addr())
	redisServer.Close()
	response := publicationRequest("")
	if response.Code != http.StatusOK {
		t.Fatal(response.Body.String())
	}
	var snapshot publicationSnapshot
	if err := json.Unmarshal(response.Body.Bytes(), &snapshot); err != nil {
		t.Fatal(err)
	}
	assertPublicationCounts(t, snapshot)
}

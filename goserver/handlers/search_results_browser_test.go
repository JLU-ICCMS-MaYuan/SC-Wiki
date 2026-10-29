package handlers

import (
	"github.com/gin-gonic/gin"
	"gorm.io/driver/mysql"
	"gorm.io/gorm"
	"net/http"
	"os"
	"scwiki/server/database"
	"strings"
	"testing"
)

// 正式Go查询＋隔离MySQL；仅详情内容以夹具供正式React路由阅读，零业务库写入。
func TestSearchBrowserFixture(t *testing.T) {
	if os.Getenv("SEARCH_RESULTS_BROWSER") != "1" {
		t.Skip("browser fixture only")
	}
	dsn := os.Getenv("SEARCH_RESULTS_TEST_DSN")
	if !strings.Contains(dsn, "/scwiki_issue178_test_") {
		t.Fatal("refusing non-test database")
	}
	db, err := gorm.Open(mysql.Open(dsn), &gorm.Config{})
	if err != nil {
		t.Fatal(err)
	}
	database.DB = db
	r := gin.New()
	r.POST("/api/papers/search/results", SearchResults)
	r.POST("/api/rag/structural-records/search", func(c *gin.Context) { c.JSON(200, gin.H{"items": []any{}, "total": 0}) })
	r.GET("/api/papers/:id", func(c *gin.Context) {
		var row struct {
			ID    int
			Title string
			DOI   string
			Year  int
		}
		db.Table("papers").Where("id=?", c.Param("id")).Scan(&row)
		states := []resultSummary{}
		db.Table("material_states AS ms").Joins("LEFT JOIN superconductors AS sc ON sc.id=ms.superconductor_id").Select("ms.id AS state_id,ms.state_key,sc.chemical_formula AS material,ms.pressure_value_gpa AS pressure_g_pa,ms.reported_space_group_symbol AS space_group,ms.reported_space_group_number AS space_group_number,ms.structure_optimization").Where("ms.paper_id=?", row.ID).Scan(&states)
		items := []gin.H{}
		for _, s := range states {
			items = append(items, gin.H{"id": s.StateID, "state_key": s.StateKey, "material": s.Material, "pressure_value_gpa": s.PressureGPa, "reported_space_group_symbol": s.SpaceGroup, "reported_space_group_number": s.SpaceGroupNumber, "structure_optimization": s.StructureOptimization, "property_modules": []any{}, "structures": []any{}})
		}
		c.JSON(200, gin.H{"id": row.ID, "title": row.Title, "doi": row.DOI, "year": row.Year, "review_status": "approved", "material_states": items})
	})
	r.GET("/api/rag/structural-records/paper/:id", func(c *gin.Context) { c.JSON(200, gin.H{"items": []any{}}) })
	r.GET("/api/rag/structural-records/:id", func(c *gin.Context) {
		c.JSON(200, gin.H{"id": c.Param("id"), "kind": "model", "material": "LaSc2H24", "pressure_gpa": 300, "space_group": "P6/mmm", "paper_id": 271, "paper_revision": 1, "title": "来源论文", "data": gin.H{}})
	})
	r.GET("/api/llm/providers", func(c *gin.Context) { c.JSON(200, gin.H{"providers": []any{}}) })
	t.Log("browser fixture ready 127.0.0.1:18579")
	if err := http.ListenAndServe("127.0.0.1:18579", r); err != nil {
		t.Fatal(err)
	}
}

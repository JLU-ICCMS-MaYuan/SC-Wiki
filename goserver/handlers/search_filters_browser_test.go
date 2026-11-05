package handlers

import (
	"github.com/gin-gonic/gin"
	"gorm.io/driver/mysql"
	"gorm.io/gorm"
	"net/http"
	"os"
	"scwiki/server/database"
	"scwiki/server/middleware"
	"scwiki/server/models"
	"strings"
	"testing"
)

// 仅隔离 MySQL 与回环测试服务；不连接业务数据库或签发业务 token。
func TestSearchFilterBrowserFixture(t *testing.T) {
	if os.Getenv("SEARCH_FILTER_BROWSER") != "1" {
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
	middleware.InitJWT("search-filter-test-only")
	r := gin.New()
	viewer := func(u *models.User) gin.H {
		return gin.H{"id": u.ID, "username": u.Username, "email": u.Email, "role": u.Role, "is_approved": u.IsApproved, "is_email_verified": true, "is_admin": paperAdmin(u), "is_superadmin": u.Role == "superadmin", "account_status": "active"}
	}
	r.GET("/test-session/:role", func(c *gin.Context) {
		var u models.User
		if db.Where("username=?", c.Param("role")).First(&u).Error != nil {
			c.Status(404)
			return
		}
		token, _ := middleware.GenerateTokenForUser(u)
		c.JSON(200, gin.H{"user": viewer(&u), "token": token})
	})
	r.GET("/api/auth/me", middleware.OptionalAuth, func(c *gin.Context) {
		v, ok := c.Get("current_user")
		if !ok {
			c.Status(401)
			return
		}
		c.JSON(200, gin.H{"user": viewer(v.(*models.User))})
	})
	r.POST("/api/papers/search/results", middleware.OptionalAuth, SearchResults)
	r.GET("/api/classification-catalogs", func(c *gin.Context) {
		c.JSON(200, gin.H{"material_families": []gin.H{{"id": 1, "name": "氢基超导体", "name_zh": "氢基超导体", "name_en": "Hydrogen-based superconductor", "aliases": []string{"hydride", "hydrogen_based"}}, {"id": 2, "name": "自建家族", "name_zh": "自建家族", "name_en": "Custom family", "aliases": []string{}}}, "structure_families": []any{}, "material_dimensionalities": []any{}})
	})
	// Python 结构查询由真实 TestClient／SQLAlchemy 测试独立验证；浏览器这里只验证请求契约。
	r.POST("/api/rag/structural-records/search", func(c *gin.Context) { c.JSON(200, gin.H{"items": []any{}, "total": 0}) })
	r.NoRoute(func(c *gin.Context) { c.JSON(200, gin.H{}) })
	t.Log("browser fixture ready 127.0.0.1:18587")
	if err := http.ListenAndServe("127.0.0.1:18587", r); err != nil {
		t.Fatal(err)
	}
}

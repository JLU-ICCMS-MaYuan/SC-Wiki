package handlers

import (
	"context"
	"os"
	"strings"
	"time"

	"scwiki/server/cache"
	"scwiki/server/database"
	"scwiki/server/storage"

	"github.com/gin-gonic/gin"
)

// Readiness 只核验网站依赖，不依赖重度解析服务。
func Readiness(c *gin.Context) {
	ctx, cancel := context.WithTimeout(c.Request.Context(), 8*time.Second)
	defer cancel()
	checks := map[string]bool{"mysql": false, "redis": false, "storage": false, "schema": false}
	if database.DB != nil {
		if db, err := database.DB.DB(); err == nil {
			checks["mysql"] = db.PingContext(ctx) == nil
		}
		if expected := os.Getenv("SCWIKI_SCHEMA_HEADS"); expected != "" {
			var revisions []string
			if err := database.DB.WithContext(ctx).Raw("SELECT version_num FROM alembic_version").Scan(&revisions).Error; err == nil {
				want := strings.Split(expected, ",")
				actual := make(map[string]bool)
				for _, revision := range revisions {
					actual[revision] = true
				}
				checks["schema"] = len(actual) == len(want)
				for _, revision := range want {
					checks["schema"] = checks["schema"] && actual[revision]
				}
			}
		}
	}
	checks["redis"] = cache.Ping(ctx) == nil
	checks["storage"] = storage.Check(ctx, avatarFiles) == nil
	ready := true
	for _, ok := range checks {
		ready = ready && ok
	}
	status := 200
	if !ready {
		status = 503
	}
	c.JSON(status, gin.H{"ready": ready, "dependencies": checks})
}

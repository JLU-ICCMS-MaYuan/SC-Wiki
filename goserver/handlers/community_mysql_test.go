package handlers

import (
	"fmt"
	"github.com/gin-gonic/gin"
	"gorm.io/driver/mysql"
	"gorm.io/gorm"
	"os"
	"scwiki/server/cache"
	"scwiki/server/database"
	"scwiki/server/middleware"
	"scwiki/server/models"
	"strings"
	"testing"
	"time"
)

// 仅接受本功能显式创建的隔离测试库，不迁移业务库。
func communityMySQLFixture(t *testing.T) *communityFixture {
	t.Helper()
	dsn := os.Getenv("COMMUNITY_TEST_DSN")
	if dsn == "" {
		t.Skip("requires isolated COMMUNITY_TEST_DSN")
	}
	if !strings.Contains(dsn, "/scwiki_issue142_test_") {
		t.Fatal("refusing non-test database")
	}
	db, err := gorm.Open(mysql.Open(dsn), &gorm.Config{})
	if err != nil {
		t.Fatal(err)
	}
	database.DB = db
	cache.Connect(os.Getenv("COMMUNITY_TEST_REDIS"))
	middleware.InitJWT("community-isolated-test")
	router := gin.New()
	RegisterCommunityRoutes(router)
	suffix := fmt.Sprintf("%d", time.Now().UnixNano())
	users := []models.User{}
	for i, role := range []string{"user", "user", "admin", "superadmin"} {
		users = append(users, createGovernanceUser(t, db, fmt.Sprintf("T%d%s", i, suffix), role, "active"))
	}
	return &communityFixture{t: t, db: db, router: router, users: users}
}
func TestCommunityMySQLReadOnly(t *testing.T)  { checkCommunityReadOnly(communityMySQLFixture(t)) }
func TestCommunityMySQLRevisions(t *testing.T) { checkCommunityRevision(communityMySQLFixture(t)) }

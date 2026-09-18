package handlers

import (
	"encoding/json"
	"fmt"
	"github.com/gin-gonic/gin"
	"gorm.io/driver/mysql"
	"gorm.io/gorm"
	"gorm.io/gorm/clause"
	"net/http"
	"net/http/httptest"
	"os"
	"scwiki/server/cache"
	"scwiki/server/database"
	"scwiki/server/middleware"
	"scwiki/server/models"
	"strings"
	"sync"
	"sync/atomic"
	"testing"
	"time"
)

// 只连接专门由 verify-community.py 创建的隔离数据库，不自动迁移真实业务库。
func communityMySQLFixture(t *testing.T) *communityFixture {
	t.Helper()
	dsn := os.Getenv("COMMUNITY_TEST_DSN")
	if dsn == "" {
		t.Skip("set COMMUNITY_TEST_DSN for isolated MySQL acceptance")
	}
	if !strings.Contains(dsn, "/scwiki_community_test?") {
		t.Fatal("refusing non-test database")
	}
	db, err := gorm.Open(mysql.Open(dsn), &gorm.Config{})
	if err != nil {
		t.Fatal(err)
	}
	database.DB = db
	cache.Connect(os.Getenv("COMMUNITY_TEST_REDIS"))
	middleware.InitJWT("isolated-community-fixture-secret")
	gin.SetMode(gin.TestMode)
	router := gin.New()
	RegisterCommunityRoutes(router)
	suffix := fmt.Sprintf("%d", time.Now().UnixNano())
	users := []models.User{createGovernanceUser(t, db, "Alice"+suffix, "user", "active"), createGovernanceUser(t, db, "Bob"+suffix, "user", "active"), createGovernanceUser(t, db, "Mod"+suffix, "admin", "active")}
	return &communityFixture{t: t, db: db, router: router, users: users}
}

func TestCommunityMySQLIntegration(t *testing.T) {
	f := communityMySQLFixture(t)
	q := f.create(map[string]any{"kind": "question", "title": "真实 MySQL 科研问答", "body": strings.Repeat("🔬", 18000)}, 0)
	a := f.create(map[string]any{"kind": "answer", "question_id": q, "body": "持久化答案"}, 1)
	var workers sync.WaitGroup
	for i := 0; i < 8; i++ {
		workers.Add(1)
		go func() { defer workers.Done(); f.request("PUT", fmt.Sprintf("/entries/%d/vote", a), nil, 0, 200) }()
	}
	workers.Wait()
	if f.request("GET", fmt.Sprintf("/entries/%d", a), nil, -1, 200)["votes"] != float64(1) {
		t.Fatal("concurrent votes were duplicated")
	}
	for _, key := range []string{"H-La", "La-H", "H-La-H"} {
		f.create(map[string]any{"kind": "comment", "system_key": key, "body": "归一化同一体系"}, 0)
	}
	if f.request("GET", "/entries?kind=comment&system_key=La-H", nil, -1, 200)["total"] != float64(3) {
		t.Fatal("system normalization failed")
	}
	owner := f.users[0].ID
	title := "社区级联验收论文"
	year := 2026
	paper := models.Paper{Title: &title, Year: &year, ReviewStatus: "approved", ContentRevision: 1, UploadedBy: &owner}
	if err := f.db.Create(&paper).Error; err != nil {
		t.Fatal(err)
	}
	c := f.create(map[string]any{"kind": "comment", "paper_id": paper.ID, "body": "修改版本前的评论"}, 0)
	reply := f.create(map[string]any{"kind": "comment", "paper_id": paper.ID, "reply_to_id": c, "body": "级联清理回复"}, 1)
	f.request("POST", fmt.Sprintf("/entries/%d/reports", reply), map[string]any{"reason": "隔离举报持久化测试"}, 0, 200)
	f.db.Model(&paper).Update("content_revision", 2)
	f.request("GET", fmt.Sprintf("/entries/%d", c), nil, -1, 200)
	f.db.Model(&paper).Update("review_status", "rejected")
	f.request("GET", fmt.Sprintf("/entries/%d", c), nil, -1, 403)
	if err := f.db.Delete(&paper).Error; err != nil {
		t.Fatal(err)
	}
	var n int64
	f.db.Model(&models.CommunityEntry{}).Where("paper_id = ?", paper.ID).Count(&n)
	if n != 0 {
		t.Fatal("paper cascade failed")
	}
	f.db.Model(&models.CommunityReport{}).Where("entry_id = ?", reply).Count(&n)
	if n != 0 {
		t.Fatal("report cascade failed")
	}
	f.db.Model(&models.CommunityNotification{}).Where("entry_id = ?", reply).Count(&n)
	if n != 0 {
		t.Fatal("notification cascade failed")
	}
	f.request("POST", fmt.Sprintf("/entries/%d/moderate", q), map[string]any{"action": "hide", "reason": "验证祖先权限阻断"}, 2, 204)
	f.request("GET", fmt.Sprintf("/entries/%d", a), nil, -1, 404)
	if f.request("GET", "/notifications/unread", nil, 0, 200)["count"] != float64(0) {
		t.Fatal("hidden question notification leaked")
	}
}

func TestCommunityMySQLHideSerializesWithReply(t *testing.T) {
	f := communityMySQLFixture(t)
	root := f.create(map[string]any{"kind": "comment", "system_key": "Hg", "body": "并发隐藏的根评论"}, 0)
	hiding := f.db.Begin()
	defer hiding.Rollback()
	var locked models.CommunityEntry
	if err := hiding.Clauses(clause.Locking{Strength: "UPDATE"}).First(&locked, root).Error; err != nil {
		t.Fatal(err)
	}
	// 屏障确认发布事务已经读到隐藏前的快照，再提交隐藏。
	readSnapshot := make(chan struct{}, 1)
	callback := "community_test_reply_snapshot"
	if err := f.db.Callback().Query().After("gorm:query").Register(callback, func(tx *gorm.DB) {
		entry, ok := tx.Statement.Dest.(*models.CommunityEntry)
		_, locking := tx.Statement.Clauses["FOR"]
		if ok && !locking && entry.ID == root {
			select {
			case readSnapshot <- struct{}{}:
			default:
			}
		}
	}); err != nil {
		t.Fatal(err)
	}
	defer f.db.Callback().Query().Remove(callback)
	token, err := middleware.GenerateTokenForUser(f.users[1])
	if err != nil {
		t.Fatal(err)
	}
	req := httptest.NewRequest("POST", "/api/community/entries", strings.NewReader(fmt.Sprintf(`{"kind":"comment","system_key":"Hg","reply_to_id":%d,"body":"不应写入的回复"}`, root)))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", "Bearer "+token)
	done := make(chan *httptest.ResponseRecorder, 1)
	go func() { w := httptest.NewRecorder(); f.router.ServeHTTP(w, req); done <- w }()
	select {
	case <-readSnapshot:
	case <-time.After(5 * time.Second):
		t.Fatal("reply did not reach snapshot barrier")
	}
	select {
	case w := <-done:
		t.Fatalf("reply bypassed root lock: %d", w.Code)
	case <-time.After(100 * time.Millisecond):
	}
	if err := hiding.Model(&locked).Update("status", "hidden").Error; err != nil {
		t.Fatal(err)
	}
	if err := hiding.Commit().Error; err != nil {
		t.Fatal(err)
	}
	select {
	case w := <-done:
		if w.Code != 409 {
			t.Fatalf("reply after hide: %d %s", w.Code, w.Body.String())
		}
	case <-time.After(5 * time.Second):
		t.Fatal("reply remained blocked after hide commit")
	}
	var count int64
	if err := f.db.Model(&models.CommunityEntry{}).Where("parent_id = ?", root).Count(&count).Error; err != nil || count != 0 {
		t.Fatalf("hidden root received a reply: count=%d error=%v", count, err)
	}
}

func TestCommunityMySQLHideAnswerSerializesWithComment(t *testing.T) {
	f := communityMySQLFixture(t)
	q := f.create(map[string]any{"kind": "question", "title": "验证隐藏答案与评论并发"}, 0)
	a := f.create(map[string]any{"kind": "answer", "question_id": q, "body": "将被隐藏的答案"}, 1)
	locked, release, contending := make(chan struct{}), make(chan struct{}), make(chan struct{}, 1)
	var paused atomic.Bool
	var once sync.Once
	unblock := func() { once.Do(func() { close(release) }) }
	defer unblock()
	after, before := "community_test_moderation_lock", "community_test_contending_lock"
	f.db.Callback().Query().After("gorm:query").Register(after, func(tx *gorm.DB) {
		entry, ok := tx.Statement.Dest.(*models.CommunityEntry)
		lock, _ := tx.Statement.Clauses["FOR"].Expression.(clause.Locking)
		if ok && entry.ID == a && lock.Strength == "UPDATE" && paused.CompareAndSwap(false, true) {
			close(locked)
			<-release
		}
	})
	f.db.Callback().Query().Before("gorm:query").Register(before, func(tx *gorm.DB) {
		lock, _ := tx.Statement.Clauses["FOR"].Expression.(clause.Locking)
		if paused.Load() && tx.Statement.Table == "community_entries" && lock.Strength == "UPDATE" {
			select {
			case contending <- struct{}{}:
			default:
			}
		}
	})
	defer f.db.Callback().Query().Remove(after)
	defer f.db.Callback().Query().Remove(before)
	start := func(path string, body any, user int) <-chan *httptest.ResponseRecorder {
		data, _ := json.Marshal(body)
		token, err := middleware.GenerateTokenForUser(f.users[user])
		if err != nil {
			t.Fatal(err)
		}
		req := httptest.NewRequest("POST", "/api/community"+path, strings.NewReader(string(data)))
		req.Header.Set("Content-Type", "application/json")
		req.Header.Set("Authorization", "Bearer "+token)
		done := make(chan *httptest.ResponseRecorder, 1)
		go func() { w := httptest.NewRecorder(); f.router.ServeHTTP(w, req); done <- w }()
		return done
	}
	hide := start(fmt.Sprintf("/entries/%d/moderate", a), map[string]any{"action": "hide", "reason": "并发隐藏答案测试"}, 2)
	select {
	case <-locked:
	case <-time.After(5 * time.Second):
		t.Fatal("moderation did not lock answer")
	}
	comment := start("/entries", map[string]any{"kind": "comment", "answer_id": a, "body": "隐藏期间不应写入"}, 0)
	select {
	case <-contending:
	case <-time.After(5 * time.Second):
		t.Fatal("comment did not contend for target")
	}
	select {
	case w := <-comment:
		t.Fatalf("comment bypassed ancestor lock: %d", w.Code)
	case <-time.After(100 * time.Millisecond):
	}
	unblock()
	for _, result := range []struct {
		response <-chan *httptest.ResponseRecorder
		want     int
	}{{hide, 204}, {comment, 404}} {
		select {
		case w := <-result.response:
			if w.Code != result.want {
				t.Fatalf("concurrent moderation: %d want %d: %s", w.Code, result.want, w.Body.String())
			}
		case <-time.After(5 * time.Second):
			t.Fatal("concurrent moderation remained blocked")
		}
	}
}

// 浏览器通过真实 Go 路由读写隔离 MySQL/Redis；令牌仅写入临时夹具文件。
func TestCommunityBrowserServer(t *testing.T) {
	addr := os.Getenv("COMMUNITY_BROWSER_ADDR")
	if addr == "" {
		t.Skip("browser fixture not requested")
	}
	f := communityMySQLFixture(t)
	users := []gin.H{}
	for _, u := range f.users {
		token, err := middleware.GenerateTokenForUser(u)
		if err != nil {
			t.Fatal(err)
		}
		users = append(users, gin.H{"token": token, "user": u})
	}
	title := "Hg 浏览器验收论文"
	year := 2026
	paper := models.Paper{Title: &title, Year: &year, ReviewStatus: "approved", ContentRevision: 1, UploadedBy: &f.users[0].ID}
	if err := f.db.Create(&paper).Error; err != nil {
		t.Fatal(err)
	}
	if err := f.db.Create(&models.ChemicalSystem{PaperID: paper.ID, PaperRevision: 1, SystemKey: "Hg", ElementsList: `["Hg"]`, ElementCount: 1}).Error; err != nil {
		t.Fatal(err)
	}
	fixture := gin.H{"users": users, "paper_id": paper.ID}
	data, _ := json.Marshal(fixture)
	if err := os.WriteFile(os.Getenv("COMMUNITY_BROWSER_FIXTURE"), data, 0600); err != nil {
		t.Fatal(err)
	}
	f.router.GET("/api/auth/me", middleware.AuthRequired, GetCurrentUser)
	f.router.GET("/api/papers/:id", middleware.OptionalAuth, GetPaper)
	f.router.GET("/api/community/contributions", middleware.OptionalAuth, CommunityContributions)
	f.router.GET("/api/papers/stats/tc-pressure", TcPressureChart)
	f.router.GET("/api/papers/stats/tc-year", TcYearChart)
	f.router.POST("/api/papers/search/records", SearchRecords)
	// 只为非社区的空目录/供应商配置提供无外部依赖的夹具。
	f.router.GET("/api/classifications", func(c *gin.Context) { c.JSON(200, gin.H{"material_families": []any{}, "structure_families": []any{}}) })
	f.router.NoRoute(func(c *gin.Context) { c.JSON(200, gin.H{"items": []any{}, "data": gin.H{}, "total": 0}) })
	if err := http.ListenAndServe(addr, f.router); err != nil {
		t.Fatal(err)
	}
}

package handlers

import (
	"encoding/json"
	"fmt"
	"github.com/alicebob/miniredis/v2"
	"github.com/gin-gonic/gin"
	"gorm.io/gorm"
	"net/http/httptest"
	"scwiki/server/cache"
	"scwiki/server/middleware"
	"scwiki/server/models"
	"strings"
	"testing"
	"time"
)

type communityFixture struct {
	t      *testing.T
	db     *gorm.DB
	router *gin.Engine
	users  []models.User
	redis  *miniredis.Miniredis
}

func newCommunityFixture(t *testing.T) *communityFixture {
	t.Helper()
	db := governanceTestDB(t)
	if err := db.AutoMigrate(&models.Paper{}, &models.ChemicalSystem{}, &models.CommunitySystem{}, &models.CommunityEntry{}, &models.CommunityVote{}, &models.CommunityReport{}, &models.CommunityModerationEvent{}, &models.CommunityNotification{}, &models.CommunityEntryRevision{}); err != nil {
		t.Fatal(err)
	}
	db.Exec("CREATE TABLE periodic_table_elements (id INTEGER PRIMARY KEY, symbol TEXT UNIQUE)")
	db.Exec("INSERT INTO periodic_table_elements(symbol) VALUES ('Hg'),('H'),('La'),('O')")
	redis := miniredis.RunT(t)
	cache.Connect(redis.Addr())
	t.Cleanup(func() { cache.Connect("127.0.0.1:6379") })
	users := []models.User{createGovernanceUser(t, db, "Alice", "user", "active"), createGovernanceUser(t, db, "Bob", "user", "active"), createGovernanceUser(t, db, "Moderator", "admin", "active"), createGovernanceUser(t, db, "Owner", "superadmin", "active")}
	middleware.InitJWT("community-test-secret")
	gin.SetMode(gin.TestMode)
	r := gin.New()
	RegisterCommunityRoutes(r)
	return &communityFixture{t, db, r, users, redis}
}
func (f *communityFixture) request(method, path string, body any, user, want int) map[string]any {
	f.t.Helper()
	data, _ := json.Marshal(body)
	req := httptest.NewRequest(method, "/api/community"+path, strings.NewReader(string(data)))
	req.Header.Set("Content-Type", "application/json")
	if user >= 0 {
		token, err := middleware.GenerateTokenForUser(f.users[user])
		if err != nil {
			f.t.Fatal(err)
		}
		req.Header.Set("Authorization", "Bearer "+token)
	}
	w := httptest.NewRecorder()
	f.router.ServeHTTP(w, req)
	if w.Code != want {
		f.t.Fatalf("%s %s: status %d want %d: %s", method, path, w.Code, want, w.Body.String())
	}
	result := map[string]any{}
	if w.Body.Len() > 0 {
		if err := json.Unmarshal(w.Body.Bytes(), &result); err != nil {
			f.t.Fatal(err)
		}
	}
	return result
}
func entryID(e map[string]any) uint { return uint(e["id"].(float64)) }
func (f *communityFixture) seed(e models.CommunityEntry) uint {
	f.t.Helper()
	e.Status = "visible"
	e.ActivityAt = time.Now().UTC()
	if err := f.db.Create(&e).Error; err != nil {
		f.t.Fatal(err)
	}
	return e.ID
}
func checkCommunityReadOnly(f *communityFixture) {
	q := f.seed(models.CommunityEntry{Kind: "question", Title: "历史超导问题", Body: "原始问题", AuthorID: f.users[0].ID})
	a := f.seed(models.CommunityEntry{Kind: "answer", QuestionID: &q, Body: "历史答案", AuthorID: f.users[1].ID})
	for user := -1; user < len(f.users); user++ {
		want := 403
		if user < 0 {
			want = 401
		}
		for _, call := range []struct{ method, path string }{{"POST", "/entries"}, {"DELETE", fmt.Sprintf("/entries/%d", a)}, {"PUT", fmt.Sprintf("/entries/%d/vote", a)}, {"DELETE", fmt.Sprintf("/entries/%d/vote", a)}, {"POST", fmt.Sprintf("/entries/%d/reports", a)}} {
			f.request(call.method, call.path, map[string]any{"kind": "question", "title": "禁止发言"}, user, want)
		}
		if user != 3 {
			f.request("PATCH", fmt.Sprintf("/entries/%d", a), map[string]any{"body": "越权编辑", "revision": 1}, user, want)
			f.request("GET", "/moderation/entries", nil, user, want)
		}
		got := f.request("GET", fmt.Sprintf("/entries/%d", a), nil, user, 200)
		if got["body"] != "历史答案" || got["can_reply"] != false || got["can_delete"] != false {
			f.t.Fatal(got)
		}
	}
	f.request("PATCH", fmt.Sprintf("/entries/%d", q), map[string]any{"body": "不允许改问题", "revision": 1}, 3, 403)
}
func TestCommunityReadOnly(t *testing.T) { checkCommunityReadOnly(newCommunityFixture(t)) }
func checkCommunityRevision(f *communityFixture) {
	q := f.seed(models.CommunityEntry{Kind: "question", Title: "多模型问题", AuthorID: f.users[3].ID})
	a := f.seed(models.CommunityEntry{Kind: "answer", QuestionID: &q, Body: "AI 原始答案", Origin: "ai", ModelID: "LLM1", ModelName: "模型一", Model: "fixture"})
	got := f.request("PATCH", fmt.Sprintf("/entries/%d", a), map[string]any{"body": "人工修订", "revision": 1}, 3, 200)
	if got["revision"] != float64(2) || got["human_edited"] != true || got["author"] != nil {
		f.t.Fatal(got)
	}
	f.request("PATCH", fmt.Sprintf("/entries/%d", a), map[string]any{"body": "过期覆盖", "revision": 1}, 3, 409)
	var revision models.CommunityEntryRevision
	f.db.Where("entry_id = ?", a).First(&revision)
	if revision.Body != "AI 原始答案" {
		f.t.Fatal(revision)
	}
	f.request("POST", fmt.Sprintf("/entries/%d/moderate", a), map[string]any{"action": "hide", "reason": "测试下架原因", "revision": 2}, 2, 403)
	f.request("POST", fmt.Sprintf("/entries/%d/moderate", a), map[string]any{"action": "hide", "reason": "测试下架原因", "revision": 2}, 3, 204)
	f.request("GET", fmt.Sprintf("/entries/%d", a), nil, -1, 404)
	rows := f.request("GET", "/moderation/entries?status=hidden", nil, 3, 200)
	if rows["total"].(float64) < 1 {
		f.t.Fatal(rows)
	}
	f.request("POST", fmt.Sprintf("/entries/%d/moderate", a), map[string]any{"action": "restore", "reason": "测试恢复原因", "revision": 2}, 3, 409)
	f.request("POST", fmt.Sprintf("/entries/%d/moderate", a), map[string]any{"action": "restore", "reason": "测试恢复原因", "revision": 3}, 3, 204)
	if f.request("GET", fmt.Sprintf("/entries/%d", a), nil, -1, 200)["body"] != "人工修订" {
		f.t.Fatal("lost revision")
	}
}
func TestCommunityRevisionAndGovernance(t *testing.T) { checkCommunityRevision(newCommunityFixture(t)) }
func TestCommunityHistoricalThreads(t *testing.T) {
	f := newCommunityFixture(t)
	key := "Hg"
	f.db.Create(&models.CommunitySystem{SystemKey: key})
	root := f.seed(models.CommunityEntry{Kind: "comment", Body: "历史根评论", SystemKey: &key, AuthorID: f.users[0].ID})
	var last uint
	for i := 0; i < 23; i++ {
		last = f.seed(models.CommunityEntry{Kind: "comment", Body: fmt.Sprintf("回复%d", i), SystemKey: &key, ParentID: &root, ReplyToID: &root, AuthorID: f.users[1].ID})
	}
	got := f.request("GET", fmt.Sprintf("/entries?kind=comment&system_key=Hg&focus_id=%d", last), nil, -1, 200)
	if got["offset"] != float64(20) || len(got["context"].([]any)) != 1 {
		t.Fatal(got)
	}
	legacy := f.seed(models.CommunityEntry{Kind: "danmaku", Body: "历史弹幕", SystemKey: &key, AuthorID: f.users[0].ID})
	f.request("GET", fmt.Sprintf("/entries/%d", legacy), nil, -1, 404)
	f.request("GET", "/entries?kind=danmaku&system_key=Hg", nil, -1, 400)
	f.db.Create(&models.CommunityNotification{EntryID: last, RecipientID: f.users[0].ID, ActorID: f.users[1].ID, Kind: "reply"})
	if f.request("GET", "/notifications/unread", nil, 0, 200)["count"] != float64(1) {
		t.Fatal("historical notice missing")
	}
	f.request("PATCH", "/notifications/read", map[string]any{}, 0, 204)
}
func TestCommunitySourceVisibility(t *testing.T) {
	f := newCommunityFixture(t)
	title := "公开论文"
	revision := uint(1)
	p := models.Paper{Title: &title, ReviewStatus: "approved", ContentRevision: 1, ApprovedRevision: &revision}
	if err := f.db.Create(&p).Error; err != nil {
		t.Fatal(err)
	}
	q := f.seed(models.CommunityEntry{Kind: "question", Title: "有文献的问题", AuthorID: f.users[3].ID})
	raw, _ := json.Marshal([]map[string]any{{"id": "S1", "paper_id": p.ID, "paper_revision": 1, "title": title, "content": "不在引用列表泄露正文"}})
	a := f.seed(models.CommunityEntry{Kind: "answer", Origin: "ai", QuestionID: &q, Body: "有来源的回答 [S1]", Citations: raw})
	f.db.Model(&p).Updates(map[string]any{"review_status": "rejected", "approved_revision": nil})
	got := f.request("GET", fmt.Sprintf("/entries/%d", a), nil, -1, 200)
	if got["body"] != "" || got["sources_available"] != false || len(got["citations"].([]any)) != 0 {
		t.Fatal(got)
	}
}

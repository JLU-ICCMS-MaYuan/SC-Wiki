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
	if err := db.AutoMigrate(&models.Paper{}, &models.ChemicalSystem{}, &models.CommunitySystem{}, &models.CommunityEntry{}, &models.CommunityVote{}, &models.CommunityReport{}, &models.CommunityModerationEvent{}, &models.CommunityNotification{}); err != nil {
		t.Fatal(err)
	}
	if err := db.Exec("CREATE TABLE periodic_table_elements (id INTEGER PRIMARY KEY, symbol TEXT UNIQUE)").Error; err != nil {
		t.Fatal(err)
	}
	db.Exec("INSERT INTO periodic_table_elements(symbol) VALUES ('Hg'),('H'),('La'),('O')")
	redis := miniredis.RunT(t)
	cache.Connect(redis.Addr())
	t.Cleanup(func() { cache.Connect("127.0.0.1:6379") })
	users := []models.User{createGovernanceUser(t, db, "Alice", "user", "active"), createGovernanceUser(t, db, "Bob", "user", "active"), createGovernanceUser(t, db, "Moderator", "admin", "active")}
	middleware.InitJWT("community-test-secret")
	gin.SetMode(gin.TestMode)
	r := gin.New()
	RegisterCommunityRoutes(r)
	return &communityFixture{t, db, r, users, redis}
}
func (f *communityFixture) request(method, path string, body any, user int, want int) map[string]any {
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
	var result map[string]any
	if w.Body.Len() > 0 {
		if err := json.Unmarshal(w.Body.Bytes(), &result); err != nil {
			f.t.Fatal(err)
		}
	}
	return result
}
func entryID(e map[string]any) uint { return uint(e["id"].(float64)) }
func (f *communityFixture) create(body map[string]any, user int) uint {
	return entryID(f.request("POST", "/entries", body, user, 201))
}
func TestCommunityQuestionAnswerCommentAndNotifications(t *testing.T) {
	f := newCommunityFixture(t)
	q := f.create(map[string]any{"kind": "question", "title": "Hg 为什么超导？", "body": "讨论 $T_c$"}, 0)
	a := f.create(map[string]any{"kind": "answer", "question_id": q, "body": "第一个答案"}, 1)
	a2 := f.create(map[string]any{"kind": "answer", "question_id": q, "body": "第二个答案"}, 0)
	f.request("PUT", fmt.Sprintf("/entries/%d/vote", a2), nil, 1, 200)
	f.request("PUT", fmt.Sprintf("/entries/%d/vote", a2), nil, 1, 200)
	list := f.request("GET", fmt.Sprintf("/entries?kind=answer&question_id=%d", q), nil, -1, 200)
	first := list["items"].([]any)[0].(map[string]any)
	if entryID(first) != a2 || first["votes"] != float64(1) {
		t.Fatal(list)
	}
	for i := 0; i < 2; i++ {
		if f.request("DELETE", fmt.Sprintf("/entries/%d/vote", a2), nil, 1, 200)["votes"] != float64(0) {
			t.Fatal("vote cancellation was not idempotent")
		}
	}
	f.request("PATCH", fmt.Sprintf("/entries/%d", q), map[string]any{"title": "Hg 临界温度条件讨论"}, 0, 200)
	if f.request("GET", "/questions?q=Hg&sort=active", nil, -1, 200)["total"] != float64(1) {
		t.Fatal("edited question was not searchable")
	}
	c := f.create(map[string]any{"kind": "comment", "answer_id": a, "body": "谢谢这个解释"}, 0)
	reply := f.create(map[string]any{"kind": "comment", "answer_id": a, "reply_to_id": c, "body": "不客气，欢迎讨论"}, 1)
	n := f.request("GET", "/notifications/unread", nil, 0, 200)
	if n["count"] != float64(2) {
		t.Fatal(n)
	}
	f.request("PATCH", "/notifications/read", map[string]any{}, 0, 204)
	if f.request("GET", "/notifications/unread", nil, 0, 200)["count"] != float64(0) {
		t.Fatal("unread not cleared")
	}
	f.request("PATCH", fmt.Sprintf("/entries/%d", a), map[string]any{"body": "越权"}, 0, 403)
	f.request("DELETE", fmt.Sprintf("/entries/%d", c), nil, 0, 200)
	placeholder := f.request("GET", fmt.Sprintf("/entries/%d", c), nil, -1, 200)
	if placeholder["body"] != "" || placeholder["author"] != nil {
		t.Fatal(placeholder)
	}
	f.request("GET", fmt.Sprintf("/entries/%d", reply), nil, -1, 200)
	f.request("POST", "/entries", map[string]any{"kind": "comment", "answer_id": a, "reply_to_id": c, "body": "已删除不允许再回复"}, 1, 409)
	f.request("DELETE", fmt.Sprintf("/entries/%d", q), nil, 0, 200)
	f.request("GET", fmt.Sprintf("/entries/%d", a), nil, -1, 404)
	if f.request("GET", "/notifications", nil, 1, 200)["total"] != float64(0) {
		t.Fatal("hidden ancestor leaked notification")
	}
}
func TestCommunityTargetsPermissionsAndGovernance(t *testing.T) {
	f := newCommunityFixture(t)
	owner := f.users[0].ID
	title := "未公开论文"
	p := models.Paper{Title: &title, ReviewStatus: "rejected", UploadedBy: &owner, ContentRevision: 1}
	if err := f.db.Create(&p).Error; err != nil {
		t.Fatal(err)
	}
	comment := f.create(map[string]any{"kind": "comment", "paper_id": p.ID, "body": "论文的私有讨论"}, 0)
	f.request("GET", fmt.Sprintf("/entries?kind=comment&paper_id=%d", p.ID), nil, -1, 403)
	f.request("GET", fmt.Sprintf("/entries/%d", comment), nil, 1, 403)
	system := f.create(map[string]any{"kind": "comment", "system_key": "Hg", "body": "跨论文共享"}, 1)
	f.request("POST", "/entries", map[string]any{"kind": "comment", "system_key": "Hg", "reply_to_id": comment, "body": "不能跨目标"}, 0, 400)
	f.request("POST", "/entries", map[string]any{"kind": "comment", "system_key": "Fake", "body": "无效元素"}, 0, 400)
	f.request("POST", "/entries", map[string]any{"kind": "comment", "system_key": "Hg", "paper_id": p.ID, "body": "两个目标"}, 0, 400)
	f.request("POST", fmt.Sprintf("/entries/%d/reports", system), map[string]any{"reason": "包含不相关广告"}, 0, 200)
	f.request("POST", fmt.Sprintf("/entries/%d/moderate", system), map[string]any{"action": "hide", "reason": "确认包含广告内容"}, 0, 403)
	f.request("POST", fmt.Sprintf("/entries/%d/moderate", system), map[string]any{"action": "hide", "reason": "确认包含广告内容"}, 2, 204)
	f.request("PATCH", fmt.Sprintf("/entries/%d", system), map[string]any{"body": "试图恢复"}, 1, 404)
	if f.request("GET", fmt.Sprintf("/entries/%d", system), nil, -1, 200)["body"] != "" {
		t.Fatal("hidden body leaked")
	}
	f.request("POST", fmt.Sprintf("/entries/%d/moderate", system), map[string]any{"action": "restore", "reason": "复核后允许恢复内容"}, 2, 204)
	var count int64
	f.db.Model(&models.CommunityModerationEvent{}).Count(&count)
	if count != 2 {
		t.Fatal(count)
	}
	f.db.Model(&models.User{}).Where("id = ?", f.users[1].ID).Update("account_status", "banned")
	f.request("POST", "/entries", map[string]any{"kind": "comment", "system_key": "Hg", "body": "封禁后不可发布"}, 1, 401)
	f.db.Model(&models.User{}).Where("id = ?", f.users[1].ID).Update("account_status", "deactivated")
	entry := f.request("GET", fmt.Sprintf("/entries/%d", system), nil, -1, 200)
	if entry["author"].(map[string]any)["deactivated"] != true {
		t.Fatal(entry)
	}
	f.request("POST", "/entries", map[string]any{"kind": "comment", "system_key": "Hg", "body": "禁用账号"}, 1, 401)
}
func TestCommunityValidationAndRateLimits(t *testing.T) {
	f := newCommunityFixture(t)
	f.request("POST", "/entries", map[string]any{"kind": "question", "title": "匿名不能发布"}, -1, 401)
	f.request("POST", "/entries", map[string]any{"kind": "question", "title": "禁止伪造身份", "author_id": 99}, 0, 400)
	f.db.Model(&models.User{}).Where("id = ?", f.users[0].ID).Update("is_email_verified", false)
	f.request("POST", "/entries", map[string]any{"kind": "question", "title": "必须邮箱验证"}, 0, 403)
	f.db.Model(&models.User{}).Where("id = ?", f.users[0].ID).Update("is_email_verified", true)
	f.request("POST", "/entries", map[string]any{"kind": "comment", "system_key": "Hg", "body": strings.Repeat("字", 2001)}, 0, 400)
	for i := 0; i < 30; i++ {
		f.create(map[string]any{"kind": "comment", "system_key": "Hg", "body": fmt.Sprintf("评论 %d", i)}, 0)
	}
	f.request("POST", "/entries", map[string]any{"kind": "comment", "system_key": "Hg", "body": "超限"}, 0, 429)
	f.redis.FastForward(time.Minute)
	last := f.create(map[string]any{"kind": "comment", "system_key": "Hg", "body": "窗口已重置"}, 0)
	f.request("PATCH", fmt.Sprintf("/entries/%d", last), map[string]any{"body": "编辑评论"}, 0, 200)
	f.request("DELETE", fmt.Sprintf("/entries/%d", last), nil, 0, 200)
	list := f.request("GET", "/entries?kind=comment&system_key=Hg&limit=50", nil, -1, 200)
	if list["total"] != float64(31) || list["items"].([]any)[30].(map[string]any)["body"] != "" {
		t.Fatal(list)
	}
	f.redis.Close()
	f.request("POST", "/entries", map[string]any{"kind": "comment", "system_key": "Hg", "body": "Redis 不可用"}, 0, 503)
}

func TestCommunityRetiredDanmakuUnavailable(t *testing.T) {
	f := newCommunityFixture(t)
	root := f.create(map[string]any{"kind": "comment", "system_key": "Hg", "body": "保留的评论"}, 0)
	reply := f.create(map[string]any{"kind": "comment", "system_key": "Hg", "reply_to_id": root, "body": "保留的回复"}, 1)
	key := "Hg"
	// 直接构造升级前的记录，验证退役接口不会读取、修改或清除历史数据。
	legacy := models.CommunityEntry{Kind: "danmaku", Body: "历史弹幕留库", AuthorID: f.users[0].ID, SystemKey: &key, Status: "visible"}
	if err := f.db.Create(&legacy).Error; err != nil {
		t.Fatal(err)
	}
	for i, status := range []string{"pending", "resolved"} {
		if err := f.db.Create(&models.CommunityReport{EntryID: legacy.ID, ReporterID: f.users[i].ID, Reason: "历史弹幕举报", Status: status}).Error; err != nil {
			t.Fatal(err)
		}
	}
	if err := f.db.Create(&models.CommunityNotification{EntryID: legacy.ID, RecipientID: f.users[0].ID, ActorID: f.users[1].ID, Kind: "danmaku"}).Error; err != nil {
		t.Fatal(err)
	}
	for _, method := range []string{"GET", "POST"} {
		path := "/entries"
		if method == "GET" {
			path += "?kind=danmaku&system_key=Hg"
		}
		if got := f.request(method, path, map[string]any{"kind": "danmaku", "system_key": "Hg", "body": "不能再发布"}, 0, 400); got["code"] != "invalid_community_input" {
			t.Fatal(got)
		}
	}
	path := fmt.Sprintf("/entries/%d", legacy.ID)
	for _, call := range []struct {
		method, path string
		body         any
		user         int
	}{
		{"GET", path, nil, -1},
		{"GET", path, nil, 2},
		{"PATCH", path, map[string]any{"body": "不能修改"}, 0},
		{"DELETE", path, nil, 0},
		{"PUT", path + "/vote", nil, 1},
		{"DELETE", path + "/vote", nil, 1},
		{"POST", path + "/reports", map[string]any{"reason": "不能举报历史弹幕"}, 1},
		{"POST", path + "/moderate", map[string]any{"action": "hide", "reason": "不能管理历史弹幕"}, 2},
		{"POST", path + "/moderate", map[string]any{"action": "restore", "reason": "不能恢复历史弹幕"}, 2},
		{"GET", fmt.Sprintf("/entries?kind=comment&system_key=Hg&focus_id=%d", legacy.ID), nil, -1},
	} {
		if got := f.request(call.method, call.path, call.body, call.user, 404); got["code"] != "content_unavailable" {
			t.Fatal(got)
		}
	}
	for _, status := range []string{"pending", "resolved"} {
		f.request("POST", fmt.Sprintf("/entries/%d/reports", root), map[string]any{"reason": "普通评论仍可处理"}, 1, 200)
		if status == "resolved" {
			f.request("POST", fmt.Sprintf("/entries/%d/moderate", root), map[string]any{"action": "dismiss", "reason": "普通评论举报驳回"}, 2, 204)
		}
		got := f.request("GET", "/moderation/reports?status="+status, nil, 2, 200)
		items := got["items"].([]any)
		if got["total"] != float64(1) || len(items) != 1 || entryID(items[0].(map[string]any)["entry"].(map[string]any)) != root {
			t.Fatal(got)
		}
	}
	notices := f.request("GET", "/notifications", nil, 0, 200)
	if notices["total"] != float64(1) || notices["items"].([]any)[0].(map[string]any)["entry_id"] != float64(reply) {
		t.Fatal(notices)
	}
	if f.request("GET", "/notifications/unread", nil, 0, 200)["count"] != float64(1) {
		t.Fatal("retired content leaked into unread count")
	}
	if f.request("GET", "/entries?kind=comment&system_key=Hg", nil, -1, 200)["total"] != float64(2) {
		t.Fatal("comments or replies changed")
	}
	var retained models.CommunityEntry
	if err := f.db.First(&retained, legacy.ID).Error; err != nil || retained.Body != legacy.Body || retained.Kind != legacy.Kind || retained.Status != legacy.Status {
		t.Fatal("historical data was changed", retained, err)
	}
}

func TestCommunityCommentThreadsAndDeepNotificationFocus(t *testing.T) {
	f := newCommunityFixture(t)
	root := f.create(map[string]any{"kind": "comment", "system_key": "Hg", "body": "第一条根评论"}, 0)
	second := f.create(map[string]any{"kind": "comment", "system_key": "Hg", "body": "第二条根评论"}, 0)
	reply := f.create(map[string]any{"kind": "comment", "system_key": "Hg", "reply_to_id": root, "body": "应当显示在第一条下面"}, 1)
	list := f.request("GET", "/entries?kind=comment&system_key=Hg", nil, -1, 200)["items"].([]any)
	for i, id := range []uint{root, reply, second} {
		if entryID(list[i].(map[string]any)) != id {
			t.Fatal("replies detached from their root", list)
		}
	}
	last := reply
	for i := 0; i < 22; i++ {
		last = f.create(map[string]any{"kind": "comment", "system_key": "Hg", "reply_to_id": root, "body": fmt.Sprintf("长线程回复 %d", i)}, 1)
	}
	focused := f.request("GET", fmt.Sprintf("/entries?kind=comment&system_key=Hg&focus_id=%d", last), nil, -1, 200)
	if focused["offset"] != float64(20) {
		t.Fatal("focus did not move to target page", focused)
	}
	items := focused["items"].([]any)
	if entryID(items[len(items)-1].(map[string]any)) != last {
		t.Fatal("target missing", focused)
	}
	context := focused["context"].([]any)
	if len(context) != 1 || entryID(context[0].(map[string]any)) != root {
		t.Fatal("root context missing", focused)
	}
	first := f.request("GET", fmt.Sprintf("/entries?kind=comment&system_key=Hg&focus_id=%d&offset=0", last), nil, -1, 200)
	if first["offset"] != float64(0) {
		t.Fatal("explicit pagination ignored", first)
	}
	f.request("POST", "/entries", map[string]any{"kind": "comment", "system_key": "hg", "body": "大小写必须严格"}, 0, 400)
}

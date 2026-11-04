package handlers

import (
	"encoding/json"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/gin-gonic/gin"
	"scwiki/server/models"
)

func TestRejectedRevisionAppearsInPrivateFilterWhileApprovedPaperStaysPublic(t *testing.T) {
	db := paperDetailTestDB(t)
	if err := db.AutoMigrate(&models.PaperHistoryEvent{}); err != nil {
		t.Fatal(err)
	}
	owner := models.User{ID: 9, Email: "revision@example.test", Username: "revision"}
	db.Create(&owner)
	revision := uint(1)
	public := models.Paper{ID: 213, Title: strPtr("旧批准内容"), UploadedBy: &owner.ID,
		ReviewStatus: "approved", ContentRevision: 1, ApprovedRevision: &revision}
	if err := db.Create(&public).Error; err != nil {
		t.Fatal(err)
	}
	reviewer := models.User{ID: 10, Email: "reviewer@example.test", Username: "reviewer", Role: "admin", IsApproved: true}
	db.Create(&reviewer)
	legacy := gin.New()
	legacy.POST("/review/:id", func(c *gin.Context) { c.Set("user_email", reviewer.Email); ReviewPaper(c) })
	blocked := httptest.NewRecorder()
	legacy.ServeHTTP(blocked, httptest.NewRequest("POST", "/review/213", strings.NewReader(`{"status":"rejected"}`)))
	if blocked.Code != 409 {
		t.Fatalf("旧审核接口不能下架批准稿: %d %s", blocked.Code, blocked.Body)
	}
	for index, state := range []struct {
		holder, filter string
		revise         bool
	}{
		{"author", "rejected", true}, {"review", "pending", false}, {"published", "approved", false},
	} {
		payload, _ := json.Marshal(map[string]any{"handoff": map[string]any{"contract": "manuscript-handoff-v1", "holder": state.holder}})
		event := models.PaperHistoryEvent{PaperID: public.ID, PaperRevision: 1, EventType: "reviewed", ClassificationSnapshot: payload, ReviewComment: strPtr("本轮处理意见")}
		if err := db.Create(&event).Error; err != nil {
			t.Fatal(err)
		}
		router := gin.New()
		router.GET("/uploads", func(c *gin.Context) { c.Set("user_email", owner.Email); GetMyUploads(c) })
		router.GET("/admin", GetPapers)
		router.PATCH("/papers/:id", func(c *gin.Context) { c.Set("user_email", owner.Email); PatchPaper(c) })
		write := httptest.NewRecorder()
		router.ServeHTTP(write, httptest.NewRequest("PATCH", "/papers/213", strings.NewReader(`{"title":"未经批准的覆盖"}`)))
		if write.Code != 409 {
			t.Fatalf("直接PATCH不能改写交接中的公开图: %d %s", write.Code, write.Body)
		}
		for _, path := range []string{"/uploads", "/admin"} {
			response := httptest.NewRecorder()
			router.ServeHTTP(response, httptest.NewRequest("GET", path+"?review_status="+state.filter, nil))
			var result struct {
				Items []map[string]any
				Total int
			}
			if err := json.Unmarshal(response.Body.Bytes(), &result); err != nil {
				t.Fatal(err)
			}
			if response.Code != 200 || result.Total != 1 || len(result.Items) != 1 {
				t.Fatalf("step %d %s: %s", index, path, response.Body)
			}
			item := result.Items[0]
			if item["workflow_status"] != state.filter || item["review_status"] != "approved" {
				t.Fatalf("混淆工作稿与公开资格: %#v", item)
			}
			if path == "/uploads" && item["can_revise"] != state.revise {
				t.Fatalf("返修入口不一致: %#v", item)
			}
		}
		var reread models.Paper
		db.First(&reread, public.ID)
		if reread.ReviewStatus != "approved" || *reread.Title != "旧批准内容" || reread.ApprovedRevision == nil {
			t.Fatal("工作稿状态覆盖公开内容")
		}
		if !canViewPaper(&reread, nil) {
			t.Fatal("旧批准版被下架")
		}
	}
}

package handlers

import (
	"encoding/json"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/gin-gonic/gin"
	"scwiki/server/models"
)

func TestReviewedPapersFollowCurrentStatusWithoutDuplicatePending(t *testing.T) {
	db := paperDetailTestDB(t)
	if err := db.AutoMigrate(&models.PaperHistoryEvent{}); err != nil {
		t.Fatal(err)
	}
	author := models.User{ID: 2, Email: "author@isolated.test", Username: "author"}
	admin := models.User{ID: 7, Email: "admin@isolated.test", Username: "admin", Role: "admin", IsApproved: true}
	super := models.User{ID: 8, Email: "super@isolated.test", Username: "super", Role: "superadmin", IsApproved: true}
	for _, user := range []models.User{author, admin, super} {
		if err := db.Create(&user).Error; err != nil {
			t.Fatal(err)
		}
	}
	revision := uint(1)
	paper := models.Paper{ID: 1208, Title: strPtr("CaH6"), UploadedBy: &author.ID,
		ReviewStatus: "approved", ContentRevision: 1, ApprovedRevision: &revision}
	if err := db.Create(&paper).Error; err != nil {
		t.Fatal(err)
	}
	// 两位审核员都有旧拒绝记录，重新送审后两人都不能重复跟踪旧结果。
	for _, user := range []models.User{admin, super} {
		event := models.PaperHistoryEvent{PaperID: paper.ID, PaperRevision: 1, ActorUserID: &user.ID,
			EventType: "reviewed", ReviewStatus: strPtr("rejected"), OccurredAt: time.Now().Add(-time.Hour)}
		if err := db.Create(&event).Error; err != nil {
			t.Fatal(err)
		}
	}
	for index, holder := range []string{"author", "review", "author", "review", "published"} {
		status := map[string]string{"author": "rejected", "review": "pending", "published": "approved"}[holder]
		payload, _ := json.Marshal(map[string]any{"handoff": map[string]any{"contract": "manuscript-handoff-v1", "holder": holder}})
		event := models.PaperHistoryEvent{PaperID: paper.ID, PaperRevision: 1, ActorUserID: &author.ID,
			EventType: "reviewed", ReviewStatus: &status, ClassificationSnapshot: payload,
			OccurredAt: time.Now().Add(time.Duration(index) * time.Minute)}
		if err := db.Create(&event).Error; err != nil {
			t.Fatal(err)
		}
		for _, user := range []models.User{admin, super} {
			router := gin.New()
			router.GET("/checked", func(c *gin.Context) {
				c.Set("user_email", user.Email)
				c.Set("current_user", &user)
				GetReviewedPapers(c)
			})
			router.GET("/pending", GetPapers)
			for _, path := range []string{"/checked", "/checked?review_status=rejected", "/checked?review_status=approved", "/checked?limit=1&offset=1", "/pending?review_status=pending"} {
				r := httptest.NewRecorder()
				router.ServeHTTP(r, httptest.NewRequest("GET", path, nil))
				var body struct {
					Total int
					Items []struct {
						ID             uint
						WorkflowStatus string `json:"workflow_status"`
					}
				}
				if err := json.Unmarshal(r.Body.Bytes(), &body); err != nil || r.Code != 200 {
					t.Fatalf("%s: %d %s", path, r.Code, r.Body)
				}
				want := 0
				switch path {
				case "/checked", "/checked?limit=1&offset=1":
					if status != "pending" {
						want = 1
					}
				case "/checked?review_status=rejected":
					if status == "rejected" {
						want = 1
					}
				case "/checked?review_status=approved":
					if status == "approved" {
						want = 1
					}
				case "/pending?review_status=pending":
					if status == "pending" {
						want = 1
					}
				}
				count := want
				if path == "/checked?limit=1&offset=1" {
					count = 0
				}
				if body.Total != want || len(body.Items) != count {
					t.Fatalf("%s step %d %s: %s", user.Role, index, path, r.Body)
				}
				if count > 0 && (body.Items[0].ID != paper.ID || body.Items[0].WorkflowStatus != status) {
					t.Fatalf("历史决定覆盖当前状态: %s", r.Body)
				}
			}
		}
	}
	var count int64
	db.Model(&models.PaperHistoryEvent{}).Where("paper_id = ?", paper.ID).Count(&count)
	if count != 7 {
		t.Fatal("列表过滤不能删除旧审核历史")
	}
}

package handlers

import (
	"encoding/json"
	"github.com/gin-gonic/gin"
	"net/http/httptest"
	"scwiki/server/models"
	"testing"
	"time"
)

func TestReviewedPapersOwnershipLatestAndPagination(t *testing.T) {
	db := paperDetailTestDB(t)
	if err := db.AutoMigrate(&models.PaperHistoryEvent{}); err != nil {
		t.Fatal(err)
	}
	actor := models.User{ID: 7, Email: "reviewer@example.test", Username: "Reviewer", Role: "admin"}
	other := models.User{ID: 8, Email: "other@example.test", Username: "Other", Role: "admin"}
	db.Create(&actor)
	db.Create(&other)
	first, second, unrelated := "First checked paper", "Second checked paper", "Other reviewer only"
	for _, p := range []models.Paper{{ID: 1, Title: &first, ReviewStatus: "pending"}, {ID: 2, Title: &second, ReviewStatus: "approved"}, {ID: 3, Title: &unrelated, ReviewStatus: "approved"}} {
		if err := db.Create(&p).Error; err != nil {
			t.Fatal(err)
		}
	}
	approved, rejected := "approved", "rejected"
	now := time.Now().UTC().Truncate(time.Second)
	for _, event := range []models.PaperHistoryEvent{
		{PaperID: 1, ActorUserID: &actor.ID, EventType: "reviewed", ReviewStatus: &rejected, OccurredAt: now.Add(-time.Hour)},
		{PaperID: 1, ActorUserID: &actor.ID, EventType: "reviewed", ReviewStatus: &approved, OccurredAt: now},
		{PaperID: 1, ActorUserID: &other.ID, EventType: "reviewed", ReviewStatus: &rejected, OccurredAt: now.Add(time.Hour)},
		{PaperID: 2, ActorUserID: &actor.ID, EventType: "reviewed", ReviewStatus: &approved, OccurredAt: now.Add(-time.Minute)},
		{PaperID: 3, ActorUserID: &other.ID, EventType: "reviewed", ReviewStatus: &approved, OccurredAt: now},
		{PaperID: 3, ActorUserID: &actor.ID, EventType: "modified", OccurredAt: now},
	} {
		if err := db.Create(&event).Error; err != nil {
			t.Fatal(err)
		}
	}
	router := gin.New()
	router.GET("/reviews", func(c *gin.Context) {
		c.Set("user_email", actor.Email)
		c.Set("current_user", &actor)
		GetReviewedPapers(c)
	})
	for _, tc := range []struct {
		query        string
		total, count int
		id           uint
	}{{"", 2, 2, 1}, {"?limit=1&offset=1", 2, 1, 2}, {"?keyword=First", 1, 1, 1}, {"?review_status=rejected", 0, 0, 0}, {"?limit=-1&offset=-2", 2, 2, 1}} {
		response := httptest.NewRecorder()
		router.ServeHTTP(response, httptest.NewRequest("GET", "/reviews"+tc.query, nil))
		if response.Code != 200 {
			t.Fatal(response.Code, response.Body)
		}
		var body struct {
			Total int `json:"total"`
			Items []struct {
				ID            uint   `json:"id"`
				CheckedStatus string `json:"checked_status"`
				ReviewStatus  string `json:"review_status"`
			} `json:"items"`
		}
		if err := json.Unmarshal(response.Body.Bytes(), &body); err != nil {
			t.Fatal(err)
		}
		if body.Total != tc.total || len(body.Items) != tc.count {
			t.Fatal(tc.query, response.Body)
		}
		if tc.count > 0 && (body.Items[0].ID != tc.id || body.Items[0].CheckedStatus != "approved") {
			t.Fatal(response.Body)
		}
		if tc.id == 1 && body.Items[0].ReviewStatus != "pending" {
			t.Fatal("historical decision confused with current status")
		}
	}
	actor.Role = "user"
	db.Model(&actor).Update("role", "user")
	response := httptest.NewRecorder()
	router.ServeHTTP(response, httptest.NewRequest("GET", "/reviews", nil))
	if response.Code != 403 {
		t.Fatal("user gained review access")
	}
}

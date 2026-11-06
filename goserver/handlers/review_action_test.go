package handlers

import (
	"github.com/gin-gonic/gin"
	"net/http/httptest"
	"strings"
	"testing"
)

func TestReviewActionRequiresExplicitDecisionAndKeepsPendingHistory(t *testing.T) {
	if !isValidReviewStatus("pending") {
		t.Fatal("旧待审核历史必须可读")
	}
	for _, status := range []string{"", "pending", "forward"} {
		if isValidReviewAction(status) {
			t.Fatalf("不允许审核动作 %q", status)
		}
	}
	for _, path := range []string{"/single", "/batch"} {
		gin.SetMode(gin.TestMode)
		router := gin.New()
		if path == "/single" {
			router.POST(path, ReviewPaper)
		} else {
			router.POST(path, BatchReview)
		}
		response := httptest.NewRecorder()
		request := httptest.NewRequest("POST", path, strings.NewReader(`{"status":"pending","paper_ids":[1]}`))
		request.Header.Set("Content-Type", "application/json")
		router.ServeHTTP(response, request)
		if response.Code != 400 {
			t.Fatalf("旧客户端pending未拒绝 %s: %d", path, response.Code)
		}
	}
}

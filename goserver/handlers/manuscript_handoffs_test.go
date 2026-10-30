package handlers

import (
	"bytes"
	"github.com/DATA-DOG/go-sqlmock"
	"github.com/gin-gonic/gin"
	"net/http"
	"net/http/httptest"
	"scwiki/server/database"
	"testing"
)

func TestBatchReviewCannotBypassFormalHandoff(t *testing.T) {
	db, mock := reviewEventTestDB(t)
	old := database.DB
	database.DB = db
	t.Cleanup(func() { database.DB = old })
	paper := func() *sqlmock.Rows {
		return sqlmock.NewRows([]string{"id", "content_revision", "review_status", "uploaded_by_user_id"}).AddRow(42, 1, "pending", 99)
	}
	mock.ExpectQuery("SELECT .* FROM " + quoteIdentifier("users")).WillReturnRows(sqlmock.NewRows([]string{"id", "email"}).AddRow(7, "admin@isolated.invalid"))
	mock.ExpectQuery("SELECT .* FROM " + quoteIdentifier("papers")).WillReturnRows(paper())
	mock.ExpectBegin()
	mock.ExpectQuery("SELECT .* FROM " + quoteIdentifier("papers")).WillReturnRows(paper())
	mock.ExpectQuery("SELECT count.*JSON_EXTRACT").WithArgs(uint(42), "manuscript-handoff-v1").
		WillReturnRows(sqlmock.NewRows([]string{"count"}).AddRow(1))
	mock.ExpectRollback()
	gin.SetMode(gin.TestMode)
	router := gin.New()
	router.POST("/batch", func(c *gin.Context) { c.Set("user_email", "admin@isolated.invalid"); BatchReview(c) })
	response := httptest.NewRecorder()
	router.ServeHTTP(response, httptest.NewRequest(http.MethodPost, "/batch", bytes.NewBufferString("{\"paper_ids\":[42],\"status\":\"rejected\"}")))
	if response.Code != 409 {
		t.Fatalf("status=%d, want 409; body=%s", response.Code, response.Body)
	}
	if err := mock.ExpectationsWereMet(); err != nil {
		t.Fatal(err)
	}
}

func quoteIdentifier(value string) string { return string(rune(96)) + value + string(rune(96)) }

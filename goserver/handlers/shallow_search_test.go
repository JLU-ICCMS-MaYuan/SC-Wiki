package handlers

import (
	"encoding/json"
	"fmt"
	"github.com/gin-gonic/gin"
	"gorm.io/driver/mysql"
	"gorm.io/gorm"
	"net/http/httptest"
	"os"
	"scwiki/server/database"
	"scwiki/server/models"
	"strings"
	"testing"
)

func TestShallowPaperSearchWithoutScientificEntities(t *testing.T) {
	db := governanceTestDB(t)
	router := resultFixture(t, db)
	if err := db.Exec("INSERT INTO papers VALUES (280,1,NULL,'published','Shallow CaH6','10.1234/shallow','Journal',2026)").Error; err != nil {
		t.Fatal(err)
	}
	if err := db.Exec("INSERT INTO chemical_systems (id,system_key,paper_id,paper_revision) VALUES (5,'Ca-H',280,1)").Error; err != nil {
		t.Fatal(err)
	}
	for _, query := range []string{
		`{"keyword":"Shallow"}`,
		`{"keyword":"10.1234/shallow"}`,
		`{"elements":["Ca","H"],"mode":"elements_exact_search"}`,
		`{"formula":"CaH6","mode":"formula_search"}`,
	} {
		result := callResults(t, router, query)
		if result["papers_total"] != float64(1) || result["states_total"] != float64(0) {
			t.Fatalf("shallow paper missing: %s: %v", query, result)
		}
		rows := result["items"].([]interface{})
		if rows[0].(map[string]interface{})["matched_states"] != float64(0) {
			t.Fatal(result)
		}
	}
	for _, query := range []string{
		`{"keyword":"Shallow","pressure_min":0}`,
		`{"keyword":"Shallow","tc_min":0}`,
		`{"keyword":"Shallow","chart_only":true}`,
		`{"keyword":"Shallow","view":"states"}`,
		`{"keyword":"Shallow","year_min":2027}`,
		`{"keyword":"Shallow","material_family_id":1}`,
		`{"keyword":"Shallow","offset":1,"limit":1}`,
	} {
		result := callResults(t, router, query)
		if len(result["items"].([]interface{})) != 0 {
			t.Fatalf("%s: %v", query, result)
		}
	}
	if !canViewPaper(&models.Paper{ReviewStatus: "published"}, nil) {
		t.Fatal("published paper not public")
	}
	if canViewPaper(&models.Paper{ReviewStatus: "rejected"}, nil) {
		t.Fatal("rejected paper became public")
	}
}

func TestShallowPublishedMySQL(t *testing.T) {
	dsn := os.Getenv("SCWIKI_SHALLOW_MYSQL_DSN")
	if dsn == "" {
		t.Skip("requires isolated SCWIKI_SHALLOW_MYSQL_DSN")
	}
	if !strings.Contains(dsn, "/scwiki_issue241_test_") {
		t.Fatal("refusing non-test database")
	}
	db, err := gorm.Open(mysql.Open(dsn), &gorm.Config{})
	if err != nil {
		t.Fatal(err)
	}
	database.DB = db
	var paper models.Paper
	if err = db.Where("review_status='published'").First(&paper).Error; err != nil {
		t.Fatal(err)
	}
	router := gin.New()
	router.POST("/results", SearchResults)
	router.GET("/papers/:id", GetPaper)
	for _, query := range []map[string]interface{}{
		{"keyword": *paper.Title}, {"formula": "CaH6", "mode": "formula_search"},
	} {
		encoded, _ := json.Marshal(query)
		result := callResults(t, router, string(encoded))
		if result["papers_total"] != float64(1) || result["states_total"] != float64(0) {
			t.Fatal(result)
		}
	}
	recorder := httptest.NewRecorder()
	router.ServeHTTP(recorder, httptest.NewRequest("GET", "/papers/"+fmt.Sprint(paper.ID), nil))
	if recorder.Code != 200 {
		t.Fatal(recorder.Code, recorder.Body.String())
	}
	var detail map[string]interface{}
	if err = json.Unmarshal(recorder.Body.Bytes(), &detail); err != nil {
		t.Fatal(err)
	}
	if detail["review_status"] != "published" || detail["parsing_mode"] != "shallow" {
		t.Fatal(detail)
	}
	if len(detail["material_states"].([]interface{})) != 0 {
		t.Fatal("fabricated scientific state")
	}
	if _, ok := detail["research_materials"]; !ok {
		t.Fatal("paper research materials missing")
	}
}

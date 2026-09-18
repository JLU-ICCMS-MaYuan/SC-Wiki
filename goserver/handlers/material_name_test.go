package handlers

import (
	"encoding/json"
	"github.com/gin-gonic/gin"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"scwiki/server/models"
)

func uintPtr(value uint) *uint { return &value }

func TestNamedStateSearchPreservesNameAndFormulaFilter(t *testing.T) {
	db := paperDetailTestDB(t)
	seedPaperFour(t, db, reviewStatusApproved)
	if err := db.Model(&models.MaterialState{}).Where("id = ?", 1).Updates(map[string]any{"superconductor_id": nil, "material_name": "Named sample"}).Error; err != nil {
		t.Fatal(err)
	}
	router := gin.New()
	router.POST("/search", SearchRecords)
	for _, query := range []string{`{"keyword":"Named sample"}`, `{"mode":"formula_search","formula":"Xe999"}`} {
		response := httptest.NewRecorder()
		req := httptest.NewRequest(http.MethodPost, "/search", strings.NewReader(query))
		req.Header.Set("Content-Type", "application/json")
		router.ServeHTTP(response, req)
		if response.Code != 200 {
			t.Fatalf("%s", response.Body.String())
		}
		var payload map[string]any
		if err := json.Unmarshal(response.Body.Bytes(), &payload); err != nil {
			t.Fatal(err)
		}
		items := payload["items"].([]any)
		if strings.Contains(query, "Xe999") {
			if len(items) != 0 {
				t.Fatal("不存在的公式不得回退成无条件搜索")
			}
		} else {
			if len(items) == 0 {
				t.Fatal("无公式状态必须可按材料名搜索")
			}
			if items[0].(map[string]any)["material_name"] != "Named sample" {
				t.Fatal("搜索结果丢失材料名")
			}
		}
	}
}

func TestNamedStateWithoutFormulaCanBeExported(t *testing.T) {
	state := models.MaterialState{ID: 1, StateKey: "tin", MaterialName: strPtr("Tin")}
	paper := models.Paper{ID: 1, ContentRevision: 1, ReviewStatus: "pending"}
	if err := validateExportCompleteness(paper, state, nil); err != nil {
		t.Fatal(err)
	}
	encoded, err := json.Marshal(materialStateExportPayload(paper, state, nil))
	if err != nil {
		t.Fatal(err)
	}
	var payload map[string]any
	if err := json.Unmarshal(encoded, &payload); err != nil {
		t.Fatal(err)
	}
	saved := payload["material_state"].(map[string]any)
	if saved["material_name"] != "Tin" || saved["material"] != "" || saved["state_key"] != "tin" {
		t.Fatalf("无公式导出失配: %#v", saved)
	}
	material := payload["material"].(map[string]any)
	if material["superconductor"] != nil || material["chemical_system"] != nil {
		t.Fatal("无公式不能伪造材料实体")
	}
}

func TestNamedStateRetainsBrokenOwnershipValidation(t *testing.T) {
	state := models.MaterialState{MaterialName: strPtr("Tin"), Superconductor: models.Superconductor{ID: 3}}
	if err := validateExportCompleteness(models.Paper{}, state, nil); err == nil {
		t.Fatal("有化学式关联时仍须验证归属")
	}
}

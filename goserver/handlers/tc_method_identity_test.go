package handlers

import (
	"encoding/json"
	"testing"

	"github.com/gin-gonic/gin"
)

func TestTcMethodOriginalSpellingsSurviveOutputProjection(t *testing.T) {
	metadata := json.RawMessage(`{"tc_contexts":{"version":2,"groups":{"g":{"parameters":{"lambda_ep":2},"calculation_conditions":{}}},"methods":{"g":{"m":{"method_code":"other","method_name":"solver A","method_raw":"old shared spelling"}}}}}`)
	records := []gin.H{
		{"method_raw": "short name", "payload": json.RawMessage(`{"tc_group":{"group_key":"g","method_key":"m"},"parameters":{"mu_star":0.1},"tc_context_ref":{"version":1,"group_key":"g","method_key":"m","method_raw_owner":"point","method_name_present":true}}`)},
		{"method_raw": "full original name", "payload": json.RawMessage(`{"tc_group":{"group_key":"g","method_key":"m"},"parameters":{"mu_star":0.13},"tc_context_ref":{"version":1,"group_key":"g","method_key":"m","method_raw_owner":"point","method_name_present":true}}`)},
		{"method_raw": nil, "payload": json.RawMessage(`{"parameters":{"mu_star":0.16},"tc_context_ref":{"version":1,"group_key":"g","method_key":"m"}}`)},
	}
	expandTcContexts(metadata, records)
	for i, expected := range []string{"short name", "full original name", "old shared spelling"} {
		if records[i]["method_raw"] != expected || records[i]["method_code"] != "other" {
			t.Fatalf("point %d lost method original: %#v", i, records[i])
		}
	}
	identity := records[0]["payload"].(map[string]interface{})["tc_group"].(map[string]interface{})
	if identity["method_name"] != "solver A" {
		t.Fatalf("lost common method description: %#v", identity)
	}
}

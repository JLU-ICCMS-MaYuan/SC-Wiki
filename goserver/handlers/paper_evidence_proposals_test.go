package handlers

import (
	"encoding/json"
	"errors"
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestProposalSaveValidationPropagatesVersionConflict(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/api/rag/evidence/proposals/validate-save" || r.Header.Get("Authorization") != "Bearer test" {
			t.Error("准备校验请求没有转发身份或路径")
		}
		var body map[string]interface{}
		if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
			t.Error(err)
		}
		if body["target_id"] != "29" || body["preparation_id"] != "prepared" || body["stage"] != "paper" {
			t.Error("准备校验缺少目标或阶段")
		}
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(409)
		_, _ = w.Write([]byte(`{"detail":{"code":"evidence_stale","message":"并发修改"}}`))
	}))
	defer server.Close()
	t.Setenv("PYTHON_BACKEND_URL", server.URL)
	err := validatePaperProposalSave(29, "Bearer test", "prepared")
	var conflict *evidencePrepareError
	if !errors.As(err, &conflict) || conflict.Status != 409 {
		t.Fatalf("应保留版本冲突: %v", err)
	}
}

func TestProposalDecisionSurvivesReviewContract(t *testing.T) {
	var record evidenceReviewRecord
	raw := []byte(`{"item_key":"summary","status":"uncertain","decision":{"actor_user_id":7,"ai_status":"unsupported","original_value":"4.29 K","final_value":"测量温度 4.29 K","reason":"原文定义"},"proposal":{"values":{"":"测量温度 4.29 K"}}}`)
	if err := json.Unmarshal(raw, &record); err != nil {
		t.Fatal(err)
	}
	encoded, err := json.Marshal(record)
	if err != nil {
		t.Fatal(err)
	}
	var output map[string]json.RawMessage
	if err := json.Unmarshal(encoded, &output); err != nil {
		t.Fatal(err)
	}
	if string(output["decision"]) != string(record.Decision) || string(output["proposal"]) != string(record.Proposal) {
		t.Fatal("审核历史丢失建议或人工决定")
	}
}

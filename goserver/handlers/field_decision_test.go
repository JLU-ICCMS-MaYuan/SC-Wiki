package handlers

import (
	"encoding/json"
	"testing"
)

func TestFieldDecisionRequiresCurrentServerContract(t *testing.T) {
	r := evidenceReviewRecord{Status: "supported", ContentHash: "value", SourceHash: "source"}
	r.FieldDecision = json.RawMessage(`{"contract":"field-review-v2","action":"approve","actor_user_id":7,"content_hash":"value","source_hash":"source"}`)
	if !validFieldDecision(r) {
		t.Fatal("有效人工决定不应要求额外理由")
	}
	r.ContentHash = "edited"
	if validFieldDecision(r) {
		t.Fatal("旧人工决定不能覆盖新值")
	}
	r.ContentHash = "value"
	r.FieldDecision = json.RawMessage(`{"action":"approve","actor_user_id":7,"content_hash":"value","source_hash":"source","reason":"我确认"}`)
	if validFieldDecision(r) {
		t.Fatal("旧人工标记不能替代新决定契约")
	}
}

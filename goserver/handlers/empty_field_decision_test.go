package handlers

import (
	"encoding/json"
	"testing"
)

func TestEmptyFieldDecisionKeepsMaterialBindingAndActualEmptyValue(t *testing.T) {
	decision := json.RawMessage(`{"contract":"field-review-v2","action":"approve","mode":"empty","actor_user_id":7,"content_hash":"c","source_hash":"s","manual_evidence_hash":"basis"}`)
	for _, value := range []string{`[]`, `null`, `""`, `{}`} {
		row := evidenceReviewRecord{FieldDecision: decision, EmptyAllowed: true, ManualEvidenceComplete: true,
			ManualEvidenceHash: "basis", CurrentValue: json.RawMessage(value), Status: "supported", ContentHash: "c", SourceHash: "s"}
		if !validFieldDecision(row) {
			t.Fatalf("合法空值未通过: %s", value)
		}
		row.ManualEvidenceHash = "changed"
		if validFieldDecision(row) {
			t.Fatal("资料变化后旧确认不应通过")
		}
	}
	for _, value := range []string{`0`, `false`, `"unknown"`, `["kept"]`} {
		row := evidenceReviewRecord{FieldDecision: decision, EmptyAllowed: true, ManualEvidenceComplete: true,
			ManualEvidenceHash: "basis", CurrentValue: json.RawMessage(value), Status: "supported", ContentHash: "c", SourceHash: "s"}
		if validFieldDecision(row) {
			t.Fatalf("非空值不应走留空: %s", value)
		}
	}
}

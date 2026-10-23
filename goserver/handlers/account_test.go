package handlers

import (
	"encoding/json"
	"scwiki/server/models"
	"testing"
)

func TestAccountProfileEmptyInterestsAreArray(t *testing.T) {
	for _, raw := range []json.RawMessage{nil, json.RawMessage("null"), json.RawMessage("[]"), json.RawMessage(`["超导"]`)} {
		encoded, err := json.Marshal(accountProfilePayload(models.User{ResearchInterests: raw}))
		if err != nil {
			t.Fatal(err)
		}
		var payload map[string]any
		if err := json.Unmarshal(encoded, &payload); err != nil {
			t.Fatal(err)
		}
		interests, ok := payload["research_interests"].([]any)
		if !ok {
			t.Fatalf("input=%s research_interests must be an array, got %#v", raw, payload["research_interests"])
		}
		if string(raw) == `["超导"]` && (len(interests) != 1 || interests[0] != "超导") {
			t.Fatal("existing interests changed")
		}
	}
}

func TestNormalizeORCID(t *testing.T) {
	for _, value := range []string{"0000-0002-1825-0097", "0000-0002-9079-593X"} {
		got, valid := normalizeORCID(value)
		if !valid || got != value {
			t.Fatalf("normalizeORCID(%q) = %q, %v", value, got, valid)
		}
	}
	for _, value := range []string{"0000-0002-1825-0098", "0000000218250097", "0000-0002-9079-5930"} {
		if _, valid := normalizeORCID(value); valid {
			t.Fatalf("normalizeORCID(%q) should fail", value)
		}
	}
	if got, valid := normalizeORCID(" "); !valid || got != "" {
		t.Fatalf("empty ORCID = %q, %v", got, valid)
	}
}

func TestNormalizeInterests(t *testing.T) {
	got, valid := normalizeInterests([]string{" 超导 ", "机器学习", "超导"})
	if !valid || len(got) != 2 || got[0] != "超导" || got[1] != "机器学习" {
		t.Fatalf("interests = %#v, %v", got, valid)
	}
	tooMany := make([]string, 11)
	for index := range tooMany {
		tooMany[index] = "方向"
	}
	if _, valid := normalizeInterests(tooMany); valid {
		t.Fatal("more than 10 interests should fail")
	}
	if _, valid := normalizeInterests([]string{""}); valid {
		t.Fatal("empty interest should fail")
	}
	if _, valid := normalizeInterests([]string{"1234567890123456789012345678901"}); valid {
		t.Fatal("interest longer than 30 runes should fail")
	}
}

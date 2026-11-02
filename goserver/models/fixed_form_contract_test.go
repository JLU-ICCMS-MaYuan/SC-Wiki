package models

import (
	"encoding/json"
	"testing"
)

func TestFixedContractKeepsSoftwareValuesSeparate(t *testing.T) {
	record := PropertyRecord{DefinitionVersion: 2}
	payload := map[string]any{"calculation_conditions": map[string]any{
		"phonon_method": "DFPT",
		"qe":            map[string]any{"energy_cutoff": map[string]any{"value_kind": "number", "value_raw": "90", "value_number": 90, "unit_raw": "Ry"}},
		"sscha":         map[string]any{"energy_cutoff": map[string]any{"value_kind": "number", "value_raw": "80", "value_number": 80, "unit_raw": "Ry"}},
	}}
	record.PayloadJSON, _ = json.Marshal(payload)
	if err := record.BeforeSave(nil); err != nil {
		t.Fatal(err)
	}
	var reread map[string]any
	if err := json.Unmarshal(record.PayloadJSON, &reread); err != nil {
		t.Fatal(err)
	}
	conditions := reread["calculation_conditions"].(map[string]any)
	if conditions["qe"].(map[string]any)["energy_cutoff"].(map[string]any)["value_number"] != float64(90) ||
		conditions["sscha"].(map[string]any)["energy_cutoff"].(map[string]any)["value_number"] != float64(80) {
		t.Fatal("不同软件的同名参数被覆盖")
	}
}
func TestFixedContractRejectsUnknownAndRetiredPaths(t *testing.T) {
	for _, conditions := range []map[string]any{
		{"method_scope": map[string]any{"stage": "epc"}},
		{"qe": map[string]any{"invented_cutoff": 90}},
		{"vasp": map[string]any{"energy_cutoff": 850}},
		{"phonon_method": true},
	} {
		raw, _ := json.Marshal(map[string]any{"calculation_conditions": conditions})
		record := PropertyRecord{DefinitionVersion: 2, PayloadJSON: raw}
		if record.BeforeSave(nil) == nil {
			t.Fatalf("异常字段被放行：%v", conditions)
		}
	}
}

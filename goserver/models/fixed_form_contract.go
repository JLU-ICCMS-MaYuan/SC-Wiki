package models

import (
	"bytes"
	_ "embed"
	"encoding/json"
	"fmt"
	"gorm.io/gorm"
	"math"
)

//go:embed scientific_form_contract.v1.json
var scientificFormContractJSON []byte

var scientificFormContract = func() struct {
	ConditionFields map[string]string   `json:"condition_fields"`
	Software        map[string][]string `json:"software"`
	QuantityFields  []string            `json:"quantity_fields"`
	PayloadFields   []string            `json:"payload_fields"`
} {
	var result struct {
		ConditionFields map[string]string   `json:"condition_fields"`
		Software        map[string][]string `json:"software"`
		QuantityFields  []string            `json:"quantity_fields"`
		PayloadFields   []string            `json:"payload_fields"`
	}
	if err := json.Unmarshal(scientificFormContractJSON, &result); err != nil {
		panic(err)
	}
	return result
}()

func containsField(fields []string, key string) bool {
	for _, value := range fields {
		if value == key {
			return true
		}
	}
	return false
}

func validateConditionValue(parameter string, raw any) error {
	if raw == nil {
		return nil
	}
	switch value := raw.(type) {
	case string:
		return nil
	case json.Number:
		number, err := value.Float64()
		if err != nil || number < 0 || math.IsNaN(number) || math.IsInf(number, 0) || parameter == "atoms" && math.Trunc(number) != number {
			return fmt.Errorf("%s数值无效", parameter)
		}
	case float64:
		if value < 0 || math.IsNaN(value) || math.IsInf(value, 0) || parameter == "atoms" && math.Trunc(value) != value {
			return fmt.Errorf("%s数值无效", parameter)
		}
	case int:
		if value < 0 {
			return fmt.Errorf("%s数值无效", parameter)
		}
	case int64:
		if value < 0 {
			return fmt.Errorf("%s数值无效", parameter)
		}
	case []any:
		if !containsField([]string{"k_grid", "q_grid", "q_grid_interpolated", "supercell", "temperature_k"}, parameter) {
			return fmt.Errorf("%s不接受数组", parameter)
		}
		for _, item := range value {
			if err := validateConditionValue(parameter, item); err != nil {
				return err
			}
		}
	case map[string]any:
		for child := range value {
			if !containsField(scientificFormContract.QuantityFields, child) {
				return fmt.Errorf("%s子键未登记", parameter)
			}
		}
		if kind := value["value_kind"]; kind != nil && kind != "number" && kind != "range" && kind != "text" {
			return fmt.Errorf("%s值类型无效", parameter)
		}
		if value["value_kind"] == "number" && value["value_raw"] != nil && value["value_raw"] != "" && value["value_number"] == nil {
			return fmt.Errorf("%s数值不完整", parameter)
		}
		for _, name := range []string{"value_number", "value_min", "value_max"} {
			switch value[name].(type) {
			case nil, json.Number, float64, int, int64:
			default:
				return fmt.Errorf("%s必须是数值", name)
			}
			if err := validateConditionValue(parameter, value[name]); err != nil {
				return err
			}
		}
		for _, name := range []string{"value_raw", "value_text", "unit_raw"} {
			if value[name] != nil {
				if _, ok := value[name].(string); !ok {
					return fmt.Errorf("%s必须是文本", name)
				}
			}
		}
		if parameter == "temperature_k" && value["unit_raw"] != nil && value["unit_raw"] != "" && value["unit_raw"] != "K" && value["unit_raw"] != "kelvin" {
			return fmt.Errorf("temperature_k须使用K")
		}
	default:
		return fmt.Errorf("%s参数类型无效", parameter)
	}
	return nil
}

// ValidateFixedCalculationConditions与Python、前端共享同一已审查清单。
func ValidateFixedCalculationConditions(conditions map[string]any) error {
	for key, value := range conditions {
		if _, ok := scientificFormContract.ConditionFields[key]; ok {
			if value != nil {
				if _, valid := value.(string); !valid {
					return fmt.Errorf("%s必须是文本", key)
				}
			}
			continue
		}
		if fields, ok := scientificFormContract.Software[key]; ok {
			if value == nil {
				continue
			}
			group, valid := value.(map[string]any)
			if !valid {
				return fmt.Errorf("%s软件参数必须是对象", key)
			}
			for parameter, raw := range group {
				if !containsField(fields, parameter) {
					return fmt.Errorf("%s.%s参数未登记", key, parameter)
				}
				if err := validateConditionValue(parameter, raw); err != nil {
					return err
				}
			}
			continue
		}
		if key != "extensions" && key != "field_settings" {
			return fmt.Errorf("计算条件字段%s未登记或已退役", key)
		}
	}
	return nil
}

// 新版记录写入必须经过契约；旧定义只为历史数据保留。
func (record *PropertyRecord) BeforeSave(_ *gorm.DB) error {
	if record.DefinitionVersion < 2 || len(record.PayloadJSON) == 0 {
		return nil
	}
	decoder := json.NewDecoder(bytes.NewReader(record.PayloadJSON))
	decoder.UseNumber()
	var payload map[string]any
	if err := decoder.Decode(&payload); err != nil {
		return err
	}
	for key := range payload {
		if !containsField(scientificFormContract.PayloadFields, key) {
			return fmt.Errorf("科学payload字段%s未登记", key)
		}
	}
	if value, present := payload["calculation_conditions"]; present && value != nil {
		conditions, ok := value.(map[string]any)
		if !ok {
			return fmt.Errorf("计算条件必须是对象")
		}
		return ValidateFixedCalculationConditions(conditions)
	}
	return nil
}

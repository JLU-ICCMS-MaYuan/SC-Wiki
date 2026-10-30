package handlers

import (
	"encoding/json"
	"fmt"
	"github.com/gin-gonic/gin"
	"gorm.io/gorm"
)

// 只在输出边界展开显式共享目录，不根据方法名称合并旧结果。
func expandTcContexts(metadata json.RawMessage, records []gin.H) {
	var meta map[string]interface{}
	if json.Unmarshal(metadata, &meta) != nil {
		return
	}
	directory, ok := meta["tc_contexts"].(map[string]interface{})
	if !ok {
		return
	}
	groups, _ := directory["groups"].(map[string]interface{})
	methods, _ := directory["methods"].(map[string]interface{})
	for _, record := range records {
		raw, _ := record["payload"].(json.RawMessage)
		var payload map[string]interface{}
		if json.Unmarshal(raw, &payload) != nil {
			continue
		}
		ref, ok := payload["tc_context_ref"].(map[string]interface{})
		if !ok {
			continue
		}
		groupKey, _ := ref["group_key"].(string)
		methodKey, _ := ref["method_key"].(string)
		group, ok := groups[groupKey].(map[string]interface{})
		if !ok {
			continue
		}
		groupMethods, _ := methods[groupKey].(map[string]interface{})
		method, ok := groupMethods[methodKey].(map[string]interface{})
		if !ok {
			continue
		}
		parameters := make(map[string]interface{})
		if shared, ok := group["parameters"].(map[string]interface{}); ok {
			for key, value := range shared {
				parameters[key] = value
			}
		}
		if own, ok := payload["parameters"].(map[string]interface{}); ok {
			for key, value := range own {
				parameters[key] = value
			}
		}
		payload["parameters"] = parameters
		payload["calculation_conditions"] = group["calculation_conditions"]
		if layout, ok := ref["association_layout"].([]interface{}); ok {
			shared, _ := group["source_associations"].([]interface{})
			own, _ := payload["source_associations"].([]interface{})
			restored := make([]interface{}, 0, len(layout))
			for _, raw := range layout {
				index, ok := raw.(map[string]interface{})
				if !ok {
					continue
				}
				if value, ok := index["shared"].(float64); ok && int(value) >= 0 && int(value) < len(shared) {
					restored = append(restored, shared[int(value)])
				} else if value, ok := index["point"].(float64); ok && int(value) >= 0 && int(value) < len(own) {
					restored = append(restored, own[int(value)])
				}
			}
			payload["source_associations"] = restored
		}
		delete(payload, "tc_context_ref")
		record["payload"] = payload
		record["method_code"] = method["method_code"]
		record["method_raw"] = method["method_raw"]
	}
}

// SQL列表和图表按点的稳定引用读取共同方法，旧逐点值保持有界兼容。
func tcMethodSQL(db *gorm.DB, record, module string) string {
	group := fmt.Sprintf("JSON_EXTRACT(%s.payload_json, '$.tc_context_ref.group_key')", record)
	method := fmt.Sprintf("JSON_EXTRACT(%s.payload_json, '$.tc_context_ref.method_key')", record)
	if db.Dialector.Name() == "sqlite" {
		path := fmt.Sprintf("'$.tc_contexts.methods.' || JSON_QUOTE(%s) || '.' || JSON_QUOTE(%s) || '.method_code'", group, method)
		return fmt.Sprintf("COALESCE(%s.method_code, JSON_EXTRACT(%s.metadata_json, %s))", record, module, path)
	}
	path := fmt.Sprintf("CONCAT('$.tc_contexts.methods.', JSON_QUOTE(JSON_UNQUOTE(%s)), '.', JSON_QUOTE(JSON_UNQUOTE(%s)), '.method_code')", group, method)
	return fmt.Sprintf("COALESCE(%s.method_code, JSON_UNQUOTE(JSON_EXTRACT(%s.metadata_json, %s)))", record, module, path)
}

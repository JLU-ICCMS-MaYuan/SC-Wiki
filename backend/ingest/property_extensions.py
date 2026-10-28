"""开放参数和计算条件扩展的有限数值校验。"""
import math


def normalize_extracted_conditions(record):
    """仅整理新提取候选；未知结构拒绝，不猜测阶段或丢弃字段。"""
    conditions = record.get("payload", {}).get("calculation_conditions")
    if conditions is None:
        return
    if not isinstance(conditions, dict):
        raise ValueError("calculation_conditions 必须是对象")
    if "extensions" not in conditions:
        return
    items = conditions["extensions"]
    if items is None or items == {}:
        items = []
    elif isinstance(items, dict):
        # #172 的实际模型响应只多了一层明确的声子阶段分组。
        group = items.get("electron_phonon")
        if (set(items) != {"electron_phonon"} or not isinstance(group, dict)
                or set(group) != {"phonon_method"}
                or not isinstance(group["phonon_method"], str) or not group["phonon_method"].strip()):
            raise ValueError("calculation_conditions.extensions 必须是带 key 的对象数组")
        items = [{"key": "electron_phonon.phonon_method", "value_kind": "text",
                  "value_raw": group["phonon_method"]}]
    if not isinstance(items, list):
        raise ValueError("calculation_conditions.extensions 必须是数组")
    from .condition_rules import PARAMETERS
    for index, item in enumerate(items):
        if (not isinstance(item, dict) or not isinstance(item.get("key"), str)
                or not item["key"].strip()):
            raise ValueError(f"calculation_conditions.extensions[{index}] 必须是带非空 key 的对象")
        if item["key"] in PARAMETERS:
            raise ValueError(f"calculation_conditions.extensions[{index}].key 缺少计算阶段；"
                             "已知条件使用对应固定字段或 stage.parameter 扩展，不猜测软件归属")
    conditions["extensions"] = items


def extension_issues(record):
    issues = []
    for group in ("parameters", "calculation_conditions"):
        value = record.get("payload", {}).get(group)
        items = value.get("extensions") if isinstance(value, dict) else None
        if not isinstance(items, list):
            continue
        for index, item in enumerate(items):
            if not isinstance(item, dict):
                continue
            kind = item.get("value_kind")
            fields = ["value_number"] if kind == "number" else ["value_min", "value_max"] if kind == "range" else []
            invalid = any(item.get(field) is not None and (isinstance(item[field], bool) or not isinstance(item[field], (int, float)) or not math.isfinite(item[field])) for field in fields)
            raw = item.get("value_raw")
            invalid |= kind == "number" and isinstance(raw, str) and bool(raw.strip()) and item.get("value_number") is None
            invalid |= kind == "range" and isinstance(raw, str) and ".." in raw and (item.get("value_min") is None or item.get("value_max") is None)
            if not invalid and kind == "range" and item.get("value_min") is not None and item.get("value_max") is not None:
                invalid = item["value_min"] > item["value_max"]
            if invalid:
                issues.append((f"payload.{group}.extensions.{index}.value_raw", "请输入完整有效的数值或递增范围"))
    return issues

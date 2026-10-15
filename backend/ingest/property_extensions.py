"""开放参数和计算条件扩展的有限数值校验。"""
import math


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

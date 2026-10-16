"""Tc 表单分组只组织现有逐结果记录，不构成另一份科学数值。"""
from __future__ import annotations

import json
import math
import re
from decimal import Decimal


def _number(value):
    return isinstance(value, (int, float, Decimal)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0


def tc_record_issues(record):
    metadata = (record.get("payload") or {}).get("tc_group")
    if metadata is None:
        return []
    if (not isinstance(metadata, dict) or type(metadata.get("version")) is not int or metadata["version"] != 1
            or any(not isinstance(metadata.get(key), str) or not metadata[key].strip() or len(metadata[key]) > 180
                   for key in ("group_key", "method_key"))
            or ("point_key" in metadata and (not isinstance(metadata["point_key"], str) or not metadata["point_key"].strip() or len(metadata["point_key"]) > 180))):
        return [("payload.tc_group", "invalid_tc_group", "Tc 分组身份无效")]
    if record.get("record_type") != "predicted_tc" or record.get("value_kind") not in {"number", "range"}:
        return [("payload.tc_group", "invalid_tc_group", "Tc 分组只用于数值预测记录")]
    if metadata.get("point_key") and record.get("value_kind") != "number":
        return [("value_kind", "invalid_tc_point", "明确组合必须保存为单值 Tc")]
    if metadata.get("point_key") and record.get("is_representative"):
        mu = ((record.get("payload") or {}).get("parameters") or {}).get("mu_star")
        if isinstance(mu, dict):
            mu = mu.get("value_number")
        if not _number(record.get("value_number")) or not _number(mu):
            return [("is_representative", "incomplete_representative_tc", "代表结果必须明确到非负有限 Tc 和 μ* 组合")]
    return []


def _shared(record):
    payload = record.get("payload") or {}
    parameters = dict(payload.get("parameters") or {})
    parameters.pop("mu_star", None)
    extensions = [item for item in parameters.get("extensions") or []
                  if isinstance(item, dict) and item.get("key") not in {"mu_star", "mu_star_reported_range", "mu_star_reported"}]
    parameters.pop("extensions", None)
    if extensions:
        parameters["extensions"] = extensions
    return json.dumps([parameters, payload.get("calculation_conditions") or {}], ensure_ascii=False, sort_keys=True, default=str)


def tc_collection_issues(records, *, strict_representative=False):
    issues, groups, methods, points = [], {}, {}, set()
    predicted = [r for r in records if r.get("record_type") == "predicted_tc"]
    grouped = any((r.get("payload") or {}).get("tc_group") is not None for r in predicted)
    selected = [index for index, r in enumerate(records) if r.get('record_type') == 'predicted_tc' and r.get('is_representative')]
    if (strict_representative or grouped) and len(selected) > 1:
        issues.append((f"records[{selected[1]}].is_representative", "duplicate_representative_tc", "同一材料状态的预测 Tc 只能选择一个代表组合"))
    for index, record in enumerate(records):
        if strict_representative and record.get('record_type') == 'predicted_tc' and record.get('is_representative'):
            mu = ((record.get('payload') or {}).get('parameters') or {}).get('mu_star')
            if isinstance(mu, dict):
                mu = mu.get('value_number')
            if record.get('value_kind') != 'number' or not _number(record.get('value_number')) or not _number(mu):
                issues.append((f'records[{index}].is_representative', 'incomplete_representative_tc', '请明确选择具体 Tc／μ* 组合，或取消旧代表标记'))
        issues.extend((f"records[{index}].{field}", code, message) for field, code, message in tc_record_issues(record))
        metadata = (record.get("payload") or {}).get("tc_group")
        if not isinstance(metadata, dict) or tc_record_issues(record):
            continue
        group, method = metadata["group_key"], metadata["method_key"]
        shared = _shared(record)
        identity = (record.get("method_code"), record.get("definition_key"), record.get("definition_version"))
        if group in groups and groups[group] != shared:
            issues.append((f"records[{index}].payload.tc_group", "tc_group_conditions_conflict", "同一共同参数组的 λ、ωlog 或计算条件不一致，请分组"))
        groups[group] = shared
        if (group, method) in methods and methods[(group, method)] != identity:
            issues.append((f"records[{index}].method_code", "tc_method_group_conflict", "同一方法行不能绑定不同预测方法或定义"))
        methods[(group, method)] = identity
        point = metadata.get("point_key")
        if point is not None:
            if (group, point) in points:
                issues.append((f"records[{index}].payload.tc_group", "duplicate_tc_point", "Tc 组合身份重复"))
            points.add((group, point))
    return issues


def validate_tc_draft(draft):
    """转换入口保护新分组草稿；无分组历史数据保持可读。"""
    from .upload_contracts import UploadContractError
    for index, state in enumerate(draft.get("material_states") or []):
        indexed = [(mi, ri, r) for mi, m in enumerate(state.get('property_modules') or []) for ri, r in enumerate(m.get('records') or [])]
        records = [r for _, _, r in indexed]
        issues = tc_collection_issues(records)
        if issues:
            field, code, message = issues[0]
            match = re.match(r'records\[(\d+)\](.*)', field)
            if match:
                mi, ri, _ = indexed[int(match.group(1))]
                field = f'property_modules[{mi}].records[{ri}]'+match.group(2)
            raise UploadContractError(code, message, f"material_states[{index}].{field}")

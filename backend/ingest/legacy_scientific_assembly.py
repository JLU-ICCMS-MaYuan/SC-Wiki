"""将兼容解析的带证据科学候选确定性组装为校对记录。"""

from __future__ import annotations

import copy
import re
from typing import Any

from .domain_extraction import _normalize_tc_method, merge_scientific_candidates


def _pressure(state: dict) -> str | None:
    value = state.get("pressure_value_gpa")
    if value is None and state.get("pressure_min_gpa") == state.get("pressure_max_gpa"):
        value = state.get("pressure_min_gpa")
    return str(value) if value is not None else None


def _state_key(state: dict) -> tuple[str, str | None, str, str]:
    return (re.sub(r"\s+", "", str(state.get("material") or state.get("material_name") or "")).casefold(),
            _pressure(state), str(state.get("reported_space_group_symbol") or "").casefold(),
            str(state.get("state_kind") or "unknown"))


def _record_key(record: dict) -> tuple:
    return (record.get("record_type"), record.get("property_code"), record.get("method_code"),
            record.get("value_kind"), record.get("value_number"), record.get("value_min"),
            record.get("value_max"), record.get("unit_raw"), str(record.get("payload") or ""),
            re.sub(r"\s+", "", str(record.get("value_raw") or "")).casefold()
            if all(record.get(name) is None for name in ("value_number", "value_min", "value_max")) else None)


def _normalize_legacy_tc(candidate: dict) -> dict:
    """旧分段缓存的别名字段只按显式数值转换，不从自由文本猜测 Tc。"""
    result = copy.deepcopy(candidate)
    for state in result.get("material_states") or []:
        for record in state.get("tc_results") or []:
            if not isinstance(record, dict):
                continue
            if record.get("tc_value_k") is None and isinstance(record.get("value"), (int, float)):
                record["tc_value_k"] = record["value"]
            low, high = record.get("value_min"), record.get("value_max")
            if record.get("tc_value_k") is None and isinstance(low, (int, float)) and low == high:
                record["tc_value_k"] = low
            elif isinstance(low, (int, float)) and isinstance(high, (int, float)):
                record.setdefault("tc_min_k", low)
                record.setdefault("tc_max_k", high)
            if not record.get("unit_raw") and record.get("unit"):
                record["unit_raw"] = record["unit"]
            if not record.get("tc_method") and record.get("method"):
                kind = "measured_tc" if record.get("result_kind") == "experimental" else "predicted_tc"
                method = _normalize_tc_method(record["method"], kind)
                if method != "unknown":
                    record["tc_method"] = method
    return result


def _tc_signatures(states: list[dict]) -> set[tuple]:
    signatures = set()
    for state in states:
        material, pressure, *_ = _state_key(state)
        if not material or pressure is None:
            continue
        legacy = state.get("tc_results") or []
        modules = state.get("property_modules") or []
        records = [*legacy, *(record for module in modules for record in module.get("records") or []
                              if record.get("property_code") == "tc")]
        for record in records:
            value = record.get("tc_value_k", record.get("value_number"))
            minimum = record.get("tc_min_k", record.get("value_min"))
            maximum = record.get("tc_max_k", record.get("value_max"))
            if value is not None or (minimum is not None and maximum is not None):
                signatures.add((material, pressure, value, minimum if value is None else None,
                                maximum if value is None else None))
    return signatures


def _merge_evidence(target: dict, incoming: dict) -> None:
    evidence = list(target.get("evidences") or [])
    for item in [*(incoming.get("evidences") or []),
                 *([incoming["evidence"]] if incoming.get("evidence") else [])]:
        if item not in evidence:
            evidence.append(copy.deepcopy(item))
    if evidence:
        target["evidences"] = evidence


def _merge_state(target: dict, incoming: dict, issues: list[dict]) -> None:
    _merge_evidence(target, incoming)
    for name in ("material_name", "crystal_system",
                 "reported_space_group_symbol", "reported_space_group_number", "material_dimensionality"):
        value = incoming.get(name)
        if target.get(name) in (None, "", "unknown") and value not in (None, "", "unknown"):
            target[name] = copy.deepcopy(value)
        elif value not in (None, "", "unknown") and target.get(name) not in (None, "", "unknown", value):
            issues.append({"field": name, "code": "conflict", "message": "同一材料状态的候选值不一致，需人工核对"})
    for name in ("pressure_raw", "pressure_unit_raw"):
        if not target.get(name) and incoming.get(name):
            target[name] = incoming[name]
    for name in ("pressure_min_gpa", "pressure_max_gpa"):
        if target.get(name) is None and incoming.get(name) is not None:
            target[name] = incoming[name]
    modules = {module["module_code"]: module for module in target.get("property_modules") or []}
    for module in incoming.get("property_modules") or []:
        code = module["module_code"]
        if code not in modules:
            target.setdefault("property_modules", []).append(copy.deepcopy(module))
            modules[code] = target["property_modules"][-1]
            continue
        existing = {_record_key(record): record for record in modules[code].get("records") or []}
        for record in module.get("records") or []:
            key = _record_key(record)
            if key in existing:
                _merge_evidence(existing[key], record)
            else:
                copied = copy.deepcopy(record)
                modules[code].setdefault("records", []).append(copied)
                existing[key] = copied


def assemble_legacy_candidates(candidates: list[dict[str, Any]]) -> tuple[list[dict], list[dict]]:
    """同材料、压力、相的碎片合并；不同结果和未知归属均保留。"""
    normalized = [_normalize_legacy_tc(item) for item in candidates]
    expected_tc = _tc_signatures([state for item in normalized for state in item.get("material_states") or []
                                  if state.get("scope") == "current_paper"])
    fragments = merge_scientific_candidates(normalized)
    groups: dict[tuple, dict] = {}
    issues: list[dict] = []
    for fragment in fragments:
        key = _state_key(fragment)
        if key in groups:
            _merge_state(groups[key], fragment, issues)
        else:
            groups[key] = copy.deepcopy(fragment)
    # 只有相与压力唯一时，才把缺少空间群的同压力碎片归入已有状态。
    for key in list(groups):
        if key[2] or key[1] is None:
            continue
        matches = [other for other in groups if other != key and other[0] == key[0]
                   and other[1] == key[1] and other[3] == key[3] and other[2]]
        if len(matches) == 1:
            _merge_state(groups[matches[0]], groups.pop(key), issues)
    result = [state for state in groups.values() if state.get("property_modules") or state.get("structure")]
    for state_index, state in enumerate(result):
        unknown_tc_method = False
        for module in state.get("property_modules") or []:
            deduplicated: dict[tuple, dict] = {}
            for record in module.get("records") or []:
                key = _record_key(record)
                if key in deduplicated:
                    _merge_evidence(deduplicated[key], record)
                else:
                    deduplicated[key] = record
            records = list(deduplicated.values())
            for record in list(records):
                if record.get("method_code") != "unknown":
                    continue
                identity = _record_key(record)
                matches = [other for other in records if other is not record
                           and other.get("method_code") not in (None, "unknown")
                           and _record_key(other)[:2] + _record_key(other)[3:]
                           == identity[:2] + identity[3:]]
                if len(matches) == 1:
                    _merge_evidence(matches[0], record)
                    records.remove(record)
            module["records"] = records
            for record_index, record in enumerate(module.get("records") or []):
                record["record_key"] = f"legacy-{state_index}-{module['module_code']}-{record_index}"
                unknown_tc_method |= (record.get("property_code") == "tc"
                                      and record.get("method_code") in (None, "unknown"))
        if unknown_tc_method:
            issues.append({"field": f"material_states[{state_index}].tc_method", "code": "candidate_missing",
                           "message": "本文报告了 Tc，但候选没有可靠的逐条计算或测量方法对应关系"})
    missing_tc = expected_tc - _tc_signatures(result)
    for material, pressure, value, minimum, maximum in sorted(missing_tc, key=str):
        issues.append({"field": "material_states.tc", "code": "candidate_missing",
                       "message": f"{material} 在 {pressure} GPa 的 Tc 候选 {value if value is not None else f'{minimum}–{maximum}'} K 未进入草稿"})
    return result, issues

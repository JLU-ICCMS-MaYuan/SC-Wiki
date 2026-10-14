"""互补提取的数值表达和显式条件校验，保留原始报告值。"""
from __future__ import annotations

import math
import re

NUMBER = r"[+-]?\d+(?:\.\d+)?"


def normalize_parameters(record):
    parameters = record.get("payload", {}).get("parameters")
    if parameters is None:
        return
    if not isinstance(parameters, dict):
        raise ValueError("parameters 必须是对象")
    extensions = parameters.setdefault("extensions", [])
    if not isinstance(extensions, list):
        raise ValueError("parameters.extensions 必须是数组")
    for key, unit in (("lambda_ep", "1"), ("omega_log", "K"), ("mu_star", "1")):
        if key == "omega_log" and "omega_log" not in parameters and "omega_log_k" in parameters:
            parameters[key] = parameters.pop("omega_log_k")
        value = parameters.get(key)
        if value is None:
            parameters.pop(key, None)
            continue
        raw = value
        if isinstance(value, dict):
            if value.get("value_min") is not None and value.get("value_max") is not None:
                lower, upper = value["value_min"], value["value_max"]
            elif value.get("min") is not None and value.get("max") is not None:
                lower, upper = value["min"], value["max"]
            elif value.get("value_number") is not None:
                parameters[key] = float(value["value_number"])
                extensions.append({"key": key+"_reported", "value_kind": "text", "value_raw": str(raw)})
                continue
            else:
                raise ValueError("参数对象未提供可核对的值")
        elif isinstance(value, str):
            match = re.fullmatch(rf"\s*({NUMBER})\s*[-–—]\s*({NUMBER})\s*", value)
            if match:
                lower, upper = map(float, match.groups())
            else:
                number = re.fullmatch(rf"\s*({NUMBER})\s*(?:{unit})?\s*", value)
                if not number:
                    raise ValueError("参数表达不符合数值或范围契约")
                parameters[key] = float(number.group(1))
                extensions.append({"key": key+"_reported", "value_kind": "text", "value_raw": value})
                continue
        elif type(value) in (int, float) and math.isfinite(value):
            continue
        else:
            raise ValueError("参数值无效")
        lower, upper = float(lower), float(upper)
        if not all(math.isfinite(v) for v in (lower, upper)) or lower > upper:
            raise ValueError("参数范围无效")
        parameters.pop(key, None)
        extensions.append({"key": key, "name": key, "value_kind": "range", "value_raw": str(raw),
                           "value_min": lower, "value_max": upper, "unit_raw": unit})
    if not extensions:
        parameters.pop("extensions", None)


def reported_pressures(record):
    code = record.get("property_code")
    if code not in {"tc", "band_gap"}:
        return set()
    values = [record.get(k) for k in ("value_number", "value_min", "value_max") if record.get(k) is not None]
    observed = set()
    for evidence in record.get("evidences", []):
        quote = evidence["quote"]
        unit = "K" if code == "tc" else "eV"
        pattern = rf"(?P<lo>{NUMBER})\s*{unit}\s*(?:to\s*(?P<hi>{NUMBER})\s*{unit}\s*)?(?:at|@)\s*(?P<p>{NUMBER})\s*GPa"
        for match in re.finditer(pattern, quote, re.I):
            temperatures = [float(match.group("lo"))] + ([float(match.group("hi"))] if match.group("hi") else [])
            if any(math.isclose(v, t, abs_tol=1e-6) for v in values for t in temperatures):
                observed.add(float(match.group("p")))
    return observed


def resolve_reported_pressures(result):
    """只对数值紧邻 at/@ 压力的原文做确定性归属；保留原状态及绑定账本。"""
    from copy import deepcopy
    resolved, bindings = [], []
    for index, state in enumerate(result["material_states"]):
        if state.get("pressure_value_gpa") is not None or state.get("pressure_min_gpa") is not None or state.get("pressure_max_gpa") is not None:
            resolved.append(state)
            continue
        groups = {}
        for module in state["property_modules"]:
            for record in module["records"]:
                observed = reported_pressures(record)
                pressure = next(iter(observed)) if len(observed) == 1 else None
                target = groups.setdefault(pressure, [])
                found = next((m for m in target if m["module_code"] == module["module_code"]), None)
                if found is None:
                    found = {**module, "records": []}
                    target.append(found)
                found["records"].append(record)
        if not groups:
            resolved.append(state)
        for pressure, modules in groups.items():
            updated = deepcopy(state)
            updated["property_modules"] = modules
            if pressure is not None:
                updated.update(pressure_value_gpa=pressure, pressure_raw=f"{pressure:g} GPa", pressure_unit_raw="GPa")
                for module in modules:
                    for record in module["records"]:
                        for evidence in record["evidences"]:
                            if evidence not in updated["evidences"]:
                                updated["evidences"].append(deepcopy(evidence))
                bindings.append({"original_state_index":index, "material":state["material"],
                                 "original_pressure_raw":state.get("pressure_raw"), "pressure_gpa":pressure,
                                 "rule":"direct-value-at-pressure-v1", "source_blocks":[e["block_id"] for m in modules for r in m["records"] for e in r["evidences"]]})
            resolved.append(updated)
    result["material_states"] = resolved
    if bindings:
        result["_pressure_bindings"] = bindings


def validate_conditions(state, record):
    pressure = state.get("pressure_value_gpa")
    condition = record.get("payload", {}).get("calculation_conditions", {})
    reported = condition.get("pressure_gpa") if isinstance(condition, dict) else None
    if pressure is not None and reported is not None and not math.isclose(float(pressure), float(reported), abs_tol=1e-6):
        raise ValueError("物性记录与材料状态的压力不一致")
    observed = reported_pressures(record)
    if observed:
        if pressure is None:
            raise ValueError("引句已明确物性压力，但材料状态缺少对应压力")
        if not any(math.isclose(pressure, value, abs_tol=1e-6) for value in observed):
            raise ValueError("引句中的物性压力归属与材料状态冲突")

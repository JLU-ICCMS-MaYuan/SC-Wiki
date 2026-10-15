"""互补提取的数值表达和显式条件校验，保留原始报告值。"""
from __future__ import annotations

import math
import re
from copy import deepcopy

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
    reported_range = parameters.pop('mu_star_reported_range',None)
    if isinstance(reported_range,dict):
        item = {**deepcopy(reported_range),'key':'mu_star_reported_range','value_kind':'range','unit_raw':reported_range.get('unit_raw','1')}
        if item not in extensions:
            extensions.append(item)
    def append(item):
        if item not in extensions:
            extensions.append(item)

    def parse_number(raw):
        if isinstance(raw, bool):
            raise ValueError("参数不能是布尔值")
        text = str(raw).strip()
        if "," in text:
            if not re.fullmatch(r"[+-]?\d{1,3}(?:,\d{3})+(?:\.\d+)?", text):
                raise ValueError("千位分隔符无效")
            text = text.replace(",", "")
        value = float(text)
        if not math.isfinite(value) or value < 0:
            raise ValueError("参数必须是非负有限数")
        return value

    for key, unit in (("lambda_ep", "1"), ("omega_log", "K"), ("mu_star", "1")):
        if key == "omega_log" and parameters.get("omega_log") is None and "omega_log_k" in parameters:
            parameters[key] = parameters.pop("omega_log_k")
        value = parameters.get(key)
        if value is None:
            parameters.pop(key, None)
            continue
        raw = deepcopy(value)
        metadata = {"reported":raw} if isinstance(raw, dict) else {}
        raw_text = str(raw.get("value_raw", raw.get("value_number", raw))) if isinstance(raw, dict) else str(raw)
        reported_unit = str(raw.get("unit_raw", raw.get("unit", unit)) or unit) if isinstance(raw, dict) else unit
        if reported_unit not in ({"K", "kelvin"} if key == "omega_log" else {"1", "dimensionless"}):
            parameters.pop(key, None)
            append({"key":key+"_reported", "value_kind":"text", "value_raw":raw_text, "unit_raw":reported_unit, **metadata})
            continue
        if isinstance(value, dict):
            if value.get("value_min") is not None and value.get("value_max") is not None:
                lower, upper = value["value_min"], value["value_max"]
            elif value.get("min") is not None and value.get("max") is not None:
                lower, upper = value["min"], value["max"]
            elif value.get("value_number") is not None:
                parameters[key] = parse_number(value["value_number"])
                append({"key": key+"_reported", "value_kind": "text", "value_raw": raw_text, "unit_raw":reported_unit, **metadata})
                continue
            else:
                raise ValueError("参数对象未提供可核对的值")
        elif isinstance(value, str):
            match = re.fullmatch(rf"\s*({NUMBER})\s*[-–—]\s*({NUMBER})\s*", value)
            if match:
                lower, upper = map(float, match.groups())
            else:
                number = re.fullmatch(rf"\s*([+-]?(?:\d{{1,3}}(?:,\d{{3}})+|\d+)(?:\.\d+)?)\s*(?:{unit})?\s*", value)
                if not number:
                    unknown_unit = re.fullmatch(rf"\s*({NUMBER})\s+([^\d\s].*)", value)
                    if unknown_unit:
                        parameters.pop(key,None)
                        append({"key":key+"_reported","value_kind":"text","value_raw":value,"unit_raw":unknown_unit.group(2)})
                        continue
                    raise ValueError("参数表达不符合数值或范围契约")
                parameters[key] = parse_number(number.group(1))
                append({"key": key+"_reported", "value_kind": "text", "value_raw": value, "unit_raw":unit})
                continue
        elif type(value) in (int, float) and math.isfinite(value) and value >= 0:
            continue
        else:
            raise ValueError("参数值无效")
        # 范围的端点顺序不代表 Tc 配对；只有显式 inverse 才进入两端控件。
        lower, upper = sorted((float(lower), float(upper)))
        if not all(math.isfinite(v) and v >= 0 for v in (lower, upper)):
            raise ValueError("参数范围无效")
        parameters.pop(key, None)
        range_key = "mu_star_reported_range" if key == "mu_star" and not (isinstance(raw,dict) and raw.get("tc_pairing")=="inverse") else key
        append({"key": range_key, "name": key, "value_kind": "range", "value_raw": raw_text,
                "value_min": lower, "value_max": upper, "unit_raw": unit, **metadata})
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
        if state.get("pressure_value_gpa") is not None:
            resolved.append(state)
            continue
        groups = {}
        for module in state["property_modules"]:
            for record in module["records"]:
                observed = reported_pressures(record)
                condition = record.get('payload',{}).get('calculation_conditions') or {}
                explicit = condition.get('pressure_gpa') if isinstance(condition,dict) else None
                if (state.get('pressure_min_gpa') is not None or state.get('pressure_max_gpa') is not None) and explicit is None:
                    # 真正以压力范围报告的结果不能仅凭句中一个端点被降为单点。
                    observed = set()
                if not observed and type(explicit) in (int,float) and math.isfinite(explicit):
                    # 表格行的显式结果条件与叙述 at/@ 压力使用同一归属边界；不是全文广播。
                    observed = {float(explicit)}
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
                updated.update(pressure_value_gpa=pressure,pressure_min_gpa=None,pressure_max_gpa=None,
                               pressure_raw=f"{pressure:g} GPa", pressure_unit_raw="GPa")
                for module in modules:
                    for record in module["records"]:
                        for evidence in record["evidences"]:
                            if evidence not in updated["evidences"]:
                                updated["evidences"].append(deepcopy(evidence))
                bindings.append({"original_state_index":index, "material":state["material"],
                                 "original_pressure_raw":state.get("pressure_raw"), "pressure_gpa":pressure,
                                 "rule":"explicit-result-pressure-v2", "source_blocks":[e["block_id"] for m in modules for r in m["records"] for e in r["evidences"]]})
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

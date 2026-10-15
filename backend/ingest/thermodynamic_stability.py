"""热力学稳定性开放 payload 的版本化契约，不改变已发布表单定义。"""
from __future__ import annotations

import math
from typing import Any

BASES = ("formation_energy", "formation_enthalpy", "formation_gibbs", "unspecified")
STABILITY = {"stable": "稳定", "unstable": "不稳定", "unknown": "未判定"}


def stability_issues(record: dict[str, Any]) -> list[tuple[str, str]]:
    value = record.get("payload", {}).get("thermodynamic_stability")
    if value is None:
        return []
    issues: list[tuple[str, str]] = []

    def add(field: str, message: str) -> None:
        issues.append(("payload.thermodynamic_stability" + ("." + field if field else ""), message))

    if (record.get("module_code"), record.get("record_type"), record.get("property_code")) != ("thermodynamical_properties", "property", "custom"):
        add("", "稳定性记录必须使用热力学自定义性质")
    if not isinstance(value, dict):
        add("", "稳定性数据必须为对象")
        return issues
    basis = value.get("basis")
    if type(value.get("version")) is not int or value["version"] != 1 or basis not in BASES:
        add("basis", "凸包依据或版本无效")
    cases = value.get("cases")
    if not isinstance(cases, dict) or not isinstance(basis, str) or basis not in cases:
        add("cases", "当前判据数据缺失")
        return issues
    for key, entry in cases.items():
        path = f"cases.{key}"
        if key not in BASES or not isinstance(entry, dict):
            add(path, "判据数据无效")
            continue
        status = entry.get("stability")
        if status not in tuple(STABILITY):
            add(path + ".stability", "请选择稳定性")
        if entry.get("zpe") not in ("included", "excluded", "unspecified"):
            add(path + ".zpe", "请选择零点振动能口径")
        if entry.get("unit") not in ("eV/atom", "meV/atom"):
            add(path + ".unit", "请选择明确的单位")
        for field in ("above_hull", "temperature_k"):
            number = entry.get(field)
            if number is not None and (isinstance(number, bool) or not isinstance(number, (int, float)) or not math.isfinite(number) or number < 0):
                add(f"{path}.{field}", "请输入非负有限数值")
        if key in ("formation_energy", "formation_enthalpy") and (entry.get("temperature_k") != 0 or isinstance(entry.get("temperature_k"), bool)):
            add(path + ".temperature_k", "此判据温度应为 0 K")
        if status != "unstable" and entry.get("above_hull") is not None:
            add(path + ".above_hull", "仅不稳定结论记录 above-hull 数值")
        for field in ("decomposition_path", "source_description"):
            if not isinstance(entry.get(field), str):
                add(f"{path}.{field}", "必须为文本")
    current = cases.get(basis)
    if isinstance(current, dict):
        status = current.get("stability")
        expected = STABILITY.get(status) if isinstance(status, str) else None
        if record.get("value_kind") != "text" or record.get("value_raw") != expected or record.get("value_text") != expected:
            add("", "记录摘要与当前判据不一致")
    return issues

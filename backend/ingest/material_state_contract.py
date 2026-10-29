"""材料状态类型、结构优化和单份规范几何的共同契约。"""
from __future__ import annotations

import re
import math
from copy import deepcopy

STATE_KINDS = frozenset({"theoretical", "experimental", "unknown"})
STRUCTURE_OPTIMIZATIONS = frozenset({"unknown", "classical_static", "quasi_harmonic", "anharmonic_quantum", "sscha"})


class MaterialStateContractError(ValueError):
    def __init__(self, field: str, message: str):
        super().__init__(message)
        self.field = field


def state_metadata(state: dict) -> dict:
    kind = state.get("state_kind") or "unknown"
    optimization = state.get("structure_optimization") or "unknown"
    if not isinstance(kind, str) or kind not in STATE_KINDS:
        raise MaterialStateContractError("state_kind", "材料状态类型已退役或无效，请选择理论、实验或未说明")
    if not isinstance(optimization, str) or optimization not in STRUCTURE_OPTIMIZATIONS:
        raise MaterialStateContractError("structure_optimization", "结构优化核处理无效")
    if kind != "theoretical" and optimization != "unknown":
        raise MaterialStateContractError("structure_optimization", "结构优化核处理仅适用于理论状态")
    metadata = {"state_kind": kind, "structure_optimization": optimization}
    if state.get("structure_optimization_details") is not None:
        metadata["structure_optimization_details"] = optimization_details(state["structure_optimization_details"])
    return metadata


def structure_nuclear_treatment(state: dict) -> str:
    return {"unknown": "unknown", "classical_static": "classical_static", "sscha": "anharmonic_quantum", "quasi_harmonic": "quasi_harmonic", "anharmonic_quantum": "anharmonic_quantum"}[state_metadata(state)["structure_optimization"]]


def validate_single_geometries(draft: dict) -> None:
    states = draft.get("material_states") or []
    counts = [int(bool(isinstance(s.get("structure"), dict) and str(s["structure"].get("structure_text") or "").strip())) for s in states]
    for candidate in draft.get("structure_candidates") or []:
        if not isinstance(candidate, dict) or candidate.get("confirmation") != "confirmed" or candidate.get("status") != "confirmed":
            continue
        match = re.fullmatch(r"material_states\[(\d+)\]", str(candidate.get("material_state_ref") or ""))
        if match is None or int(match[1]) >= len(states):
            raise MaterialStateContractError("structure_candidates", "已确认结构必须关联有效的材料状态")
        counts[int(match[1])] += 1
    for i, count in enumerate(counts):
        if count > 1:
            raise MaterialStateContractError(f"material_states[{i}].structure", "每张状态卡只保存一份规范结构几何，不同优化几何请分别建卡；原胞、惯用胞和格式使用同一结构的派生表示")


OPTIMIZATION_DETAIL_LABELS = {
    "method": "结构优化方法", "electronic_method": "优化求力电子理论", "calculation_code": "结构优化软件",
    "temperature_k": "优化温度 (K)", "pressure_gpa": "优化外压 (GPa)",
    "centroids": "原子平均位置", "volume": "体积", "cell_shape": "晶胞形状",
}


def optimization_details(value):
    if not isinstance(value, dict):
        raise MaterialStateContractError("structure_optimization_details", "结构优化详情必须是对象")
    for key in ("centroids", "volume", "cell_shape"):
        if value.get(key) is not None and value[key] not in {"unknown", "fixed", "optimized"}:
            raise MaterialStateContractError("structure_optimization_details." + key, "几何自由度只能是未说明、固定或优化")
    for key in ("temperature_k", "pressure_gpa"):
        number = value.get(key)
        if number is not None and (type(number) not in (int, float) or not math.isfinite(number)
                or key == "temperature_k" and number < 0):
            raise MaterialStateContractError("structure_optimization_details." + key, "优化温压必须是有效数值")
    from .calculation_methods import electronic_method_issue
    issue = electronic_method_issue(value.get("electronic_method"))
    if issue:
        raise MaterialStateContractError("structure_optimization_details.electronic_method", issue)
    for key in ("method", "electronic_method", "calculation_code"):
        if value.get(key) is not None and not isinstance(value[key], str):
            raise MaterialStateContractError("structure_optimization_details." + key, "优化方法与软件必须是文本")
    return deepcopy(value)

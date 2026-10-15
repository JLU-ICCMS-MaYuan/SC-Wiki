"""材料状态类型、结构优化和单份规范几何的共同契约。"""
from __future__ import annotations

import re

STATE_KINDS = frozenset({"theoretical", "experimental", "unknown"})
STRUCTURE_OPTIMIZATIONS = frozenset({"unknown", "classical_static", "sscha"})


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
    return {"state_kind": kind, "structure_optimization": optimization}


def structure_nuclear_treatment(state: dict) -> str:
    return {"unknown": "unknown", "classical_static": "classical_static", "sscha": "anharmonic_quantum"}[state_metadata(state)["structure_optimization"]]


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

"""在原文小数舍入范围内恢复报告的位点对称约束，不放宽展开容差。"""

from __future__ import annotations

from decimal import Decimal
import re

import numpy as np


def restore_rounded_site(group, tokens: list[str], multiplicity: int) -> tuple[list[float], dict | None]:
    """以打印精度归一的最小改变量投影到唯一可兼容的稳定子约束。"""
    if len(tokens) != 3 or any(not re.fullmatch(r"[-+]?\d+(?:\.\d+)?", token) for token in tokens):
        raise ValueError("坐标必须为三项明确的小数或整数")
    point = np.array([float(token) for token in tokens])
    if len(group.get_orbit(point, tol=1e-7)) == multiplicity:
        return point.tolist(), None
    # 整数坐标按精确对称位置处理；小数按末位的一半界定舍入区间。
    bounds = np.array([float(Decimal(5).scaleb(Decimal(token).as_tuple().exponent - 1))
                       if "." in token else 0.0 for token in tokens])
    matrices, offsets = [], []
    for operation in sorted(group.symmetry_ops, key=lambda op: tuple(op.rotation_matrix.ravel()) + tuple(op.translation_vector)):
        matrix = operation.rotation_matrix - np.eye(3)
        displacement = matrix @ point + operation.translation_vector
        translation = np.rint(displacement)
        if np.all(np.abs(displacement - translation) <= np.abs(matrix) @ bounds + 1e-10):
            matrices.append(matrix)
            offsets.append(translation - operation.translation_vector)
    order = len(group.symmetry_ops)
    if multiplicity <= 0 or order % multiplicity or len(matrices) != order // multiplicity:
        raise ValueError("原文舍入范围内的位点对称约束不足或有歧义")
    matrix, offset = np.concatenate(matrices), np.concatenate(offsets)
    displacement = np.linalg.lstsq(matrix * bounds, offset - matrix @ point, rcond=None)[0]
    derived = point + bounds * displacement
    if (np.max(np.abs(displacement)) > 1 + 1e-8
            or np.max(np.abs(matrix @ derived - offset)) > 1e-9
            or len(group.get_orbit(derived, tol=1e-7)) != multiplicity):
        raise ValueError("无法在原文舍入范围内恢复报告的位点多重性")
    return derived.tolist(), {
        "rule": "reported_precision_symmetry_projection",
        "reported_tokens": tokens,
        "reported_coordinates": point.tolist(),
        "derived_coordinates": derived.tolist(),
        "rounding_half_width": bounds.tolist(),
        "coordinate_changes": (derived - point).tolist(),
        "multiplicity": multiplicity,
        "stabilizer_order": len(matrices),
    }

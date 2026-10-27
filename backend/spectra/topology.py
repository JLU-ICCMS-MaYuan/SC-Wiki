"""共享实际连线图：线性遍历诊断，不按接近程度推断连接。"""
from __future__ import annotations

import math


def point_id(curve, point, index):
    return point.get("id") or f"{curve['id']}:p{index}"


def build_graph(curve):
    points = curve.get("points") or []
    ids = [point_id(curve, p, i) for i, p in enumerate(points)]
    if len(set(ids)) != len(ids):
        raise ValueError("数据点身份重复")
    nodes = dict(zip(ids, points))
    adjacent = {key: [] for key in ids}
    known, invalid = set(), []
    for i, p in enumerate(points):
        parent = p.get("connectTo")
        if parent is None and i:
            previous = points[i - 1]
            connected = not p["breakBefore"] if "breakBefore" in p else (
                previous.get("segment") == p.get("segment") or previous.get("manual") or p.get("manual"))
            if connected:
                parent = ids[i - 1]
        for target in (parent, p.get("joinTo")):
            if target is None:
                continue
            if target not in nodes or target == ids[i]:
                invalid.append(ids[i])
                continue
            edge = frozenset((ids[i], target))
            if edge not in known:
                known.add(edge)
                adjacent[ids[i]].append(target)
                adjacent[target].append(ids[i])
    return nodes, adjacent, invalid


def graph_parts(adjacent):
    """迭代DFS：分量、真实闭环回边；不用递归，长谱不会栈溢出。"""
    color, components, cycles = {}, [], []
    for start in adjacent:
        if start in color:
            continue
        part = [start]
        color[start] = 1
        stack = [(start, None, iter(adjacent[start]))]
        while stack:
            node, parent, neighbors = stack[-1]
            target = next(neighbors, None)
            if target is None:
                color[node] = 2
                stack.pop()
            elif target != parent:
                if target not in color:
                    color[target] = 1
                    part.append(target)
                    stack.append((target, node, iter(adjacent[target])))
                elif color[target] == 1:
                    cycles.append((node, target))
        components.append(part)
    return components, cycles


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def location(curve, key, point):
    fp, ap = point.get("frequency_pixel"), point.get("amplitude_pixel")
    for name, value in (("frequency", point.get("frequency_thz")), ("amplitude", point.get("reconstructed_amplitude"))):
        axis = curve.get("axis_calibration", {}).get(name, {})
        if not finite(fp if name == "frequency" else ap) and finite(value) and finite(axis.get("slope")) and axis["slope"]:
            pixel = (value - axis.get("intercept", 0)) / axis["slope"]
            if name == "frequency":
                fp = pixel
            else:
                ap = pixel
    x, y = (ap, fp) if curve.get("frequency_direction") == "y" else (fp, ap)
    return dict(point_id=key, frequency_thz=point.get("frequency_thz") if finite(point.get("frequency_thz")) else None,
                amplitude=point.get("reconstructed_amplitude") if finite(point.get("reconstructed_amplitude")) else None,
                x=x if finite(x) else None, y=y if finite(y) else None)


def diagnose_curve(curve, document=None):
    base = dict(curve_id=curve["id"], name=curve.get("projection") or ("α²F" if curve["kind"] == "alpha2f" else curve["id"]),
                amplitude_unit=curve.get("unit", "unknown"), point_count=len(curve.get("points") or []))
    try:
        nodes, edges, invalid = build_graph(curve)
    except ValueError as exc:
        return dict(**base, component_count=0, issues=[dict(kind="invalid", message=str(exc), points=[])])
    components, cycles = graph_parts(edges)
    issues = []
    def add(kind, message, keys):
        issues.append(dict(kind=kind, message=message, points=[location(curve, k, nodes[k]) for k in keys]))
    for key in dict.fromkeys(invalid):
        add("invalid", "点的连接目标失效，请检查该点", [key])
    for key, neighbors in edges.items():
        if len(neighbors) > 2:
            # 一项一个中心点；所有分叉均列出，不复制大邻接表。
            add("branch", f"分叉点：连接了{len(neighbors)}个邻点", [key])
    for a, b in cycles:
        add("cycle", "闭环中的实际连接：检查这条边的两个端点", [a, b])
    for index, part in enumerate(components):
        if len(part) == 1:
            add("isolated", "孤立点：未连接到其他数据点", part)
        elif len(components) > 1:
            ends = [key for key in part if len(edges[key]) == 1]
            # 分叉组件可能很多端点，每项最多两个坐标，前端分页保持有界。
            for i in range(0, len(ends), 2):
                add("disconnected", f"未连接片段{index+1}（{len(part)}点）：端点仅供检查，不表示必须相互连接", ends[i:i+2])
    from .preflight import sample_issues
    issues.extend(sample_issues(curve, document))
    return dict(**base, component_count=len(components), issues=issues)


def diagnose(payload, kind):
    curves=[c for c in payload.get("curves",[]) if c["kind"]==kind]
    reports=[diagnose_curve(c,payload.get("manual_documents",{}).get(c["id"])) for c in curves]
    return dict(curves=reports)

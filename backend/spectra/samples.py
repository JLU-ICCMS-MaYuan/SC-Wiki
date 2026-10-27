"""已有谱连接/频率与数值有效性，供正式提取及重算共用。"""
import math
from . import manual
from .topology import build_graph, graph_parts
from .preflight import coincident

def demand(condition,reason):
    if not condition:raise ValueError(reason)

def connected_samples(curve, document=None):
    """线性复杂度遍历真实连接，拒绝断片/分叉/环；不按频率排序来填缺口。"""
    points = curve.get("points") or []
    demand(len(points) >= 2, "至少需要两个有效数据点")
    nodes, edges, invalid = build_graph(curve)
    demand(not invalid, "描线含失效连接")
    demand(all(len(e) <= 2 for e in edges.values()), "曲线存在分叉，请检查下方问题坐标")
    components, cycles = graph_parts(edges)
    demand(not cycles, "曲线存在闭环，请检查下方问题坐标")
    demand(len(components) == 1, "曲线存在缺口或孤立点，请检查下方未连接片段坐标")
    ends = [identity for identity, e in edges.items() if len(e) == 1]
    demand(len(ends) == 2, "曲线缺少有效端点")
    ordered, seen, current = [], set(), ends[0]
    while current not in seen:
        seen.add(current)
        ordered.append(nodes[current])
        next_ids = [key for key in edges[current] if key not in seen]
        if not next_ids:
            break
        current = next(iter(next_ids))
    demand(len(seen) == len(points), "曲线存在未连接片段，不能跨缺口积分")
    samples=[]
    for p in ordered:
        if samples and coincident(samples[-1],p):
            continue
        samples.append(p)
    ordered=samples
    demand(len(ordered)>=2, "至少需要两个不同的有效采样位置")
    f = [p.get("frequency_thz") for p in ordered]
    a = [p.get("reconstructed_amplitude") for p in ordered]
    demand(all(manual.finite(v) for v in f + a), "曲线含缺失或非有限数值")
    amplitude_axis = curve.get("axis_calibration", {}).get("amplitude", {})
    for i, point in enumerate(ordered):
        if amplitude_axis and manual.finite(point.get("amplitude_pixel")):
            terms = (amplitude_axis["slope"] * point["amplitude_pixel"], amplitude_axis["intercept"])
            error = 8 * sum(math.ulp(abs(term)) for term in terms)
            if abs(a[i]) <= error:
                a[i] = 0.  # 仅消除线性标定的浮点消去误差，不回写源数据。
    if f[0] > f[-1]:
        f.reverse()
        a.reverse()
    demand(all(y > x for x, y in zip(f, f[1:])), "曲线存在重复或回折频率，不能作为单值谱积分")
    demand(all(v >= 0 for v in a), "幅值存在负数，请核对零基线")
    # 只消除标定浮点舍入；不把邻近频率的真实数据改成零。
    tolerance = 1e-12 * max(1., abs(f[-1]))
    demand(abs(f[0]) <= tolerance, "当前曲线未从真实零频开始")
    f[0] = 0.
    if document is not None:
        demand(manual.zero_report(document)["complete"], "当前曲线的零频位置或零频点尚未确认")
    return f, a

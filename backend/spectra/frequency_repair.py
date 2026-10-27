"""原路径上的局部频率微调；原图每点0.5px上限，幅值和连线不变。"""
from __future__ import annotations

import json
import math
import uuid
from .contracts import FREQUENCY_FACTORS
from .preflight import path_points, coincident, numerical_zero
from .topology import build_graph, finite, location

MAX_SHIFT_PX = .5
MIN_STEP_PX = 1e-6
AUTO_KIND = "auto-frequency-repair"
UNDO_KIND = "undo-frequency-repair"
STATUS = "自动频率微调"


def _batches(doc):
    batches, undone = {}, set()
    for op in doc.get("operations", []):
        if op.get("kind") not in {AUTO_KIND, UNDO_KIND}:
            continue
        try:
            value = json.loads(op["detail"])
            identity = value["batch_id"]
            if not isinstance(identity, str):
                continue
            if op["kind"] == UNDO_KIND:
                undone.add(identity)
            else:
                batch = batches.setdefault(identity, {**value, "changes": []})
                batch["changes"].extend(value["changes"])
        except (KeyError, TypeError, ValueError):
            continue
    return [b for key, b in batches.items() if key not in undone]


def _active_points(curve, doc):
    numeric = {p.get("id"): p for p in curve.get("points", [])}
    changed = {}
    for batch in _batches(doc):
        if batch.get("direction") != doc["calibration"]["direction"] or batch.get("frequency_calibration") != doc["calibration"]["frequency"]:
            continue
        for entry in batch.get("changes", []):
            if not isinstance(entry, list) or len(entry) != 3:
                continue
            key, before, after = entry
            point = numeric.get(key)
            if point and finite(before) and finite(after) and 0 < abs(after-before) <= MAX_SHIFT_PX:
                changed[key] = (before, after)
    return [{**location(curve, key, numeric[key]), "before_pixel": before, "after_pixel": after,
             "shift_px": abs(after-before)} for key, (before, after) in changed.items()
            if numeric[key].get("frequency_pixel") == after]


def _blocks(values):
    """相等也合并，正常单点块不改动；栈合并为线性复杂度。"""
    blocks = []
    for i, value in enumerate(values):
        blocks.append([i, i+1, value, 1])
        while len(blocks) > 1 and blocks[-2][2]/blocks[-2][3] >= blocks[-1][2]/blocks[-1][3]:
            right = blocks.pop()
            left = blocks[-1]
            left[1] = right[1]
            left[2] += right[2]
            left[3] += right[3]
    return blocks


def _inputs(curve, doc):
    direction = curve.get("frequency_direction")
    if direction not in {"x", "y"} or doc.get("calibration", {}).get("direction") != direction:
        raise ValueError("缺少一致的频率轴方向")
    if not isinstance(doc.get("operations"), list):
        raise ValueError("缺少有效编辑操作记录")
    axis = doc["calibration"]["frequency"]
    factor = FREQUENCY_FACTORS[axis["unit"]]
    slope = (axis["values"][1]-axis["values"][0])/(axis["pixels"][1]-axis["pixels"][0])*factor
    if not finite(slope) or slope == 0:
        raise ValueError("频率标定无效")
    def frequency(pixel):
        return (axis["values"][0]+(pixel-axis["pixels"][0])*(axis["values"][1]-axis["values"][0])/
                (axis["pixels"][1]-axis["pixels"][0]))*factor
    ordered = path_points(curve)
    if not ordered:
        raise ValueError("曲线存在缺口、分叉、闭环或失效连接，未自动调整频率")
    dc = doc["curves"][0]
    _, edges, invalid = build_graph(curve)
    _, doc_edges, doc_invalid = build_graph(dc)
    if invalid or doc_invalid or edges.keys() != doc_edges.keys() or any(set(v) != set(doc_edges[k]) for k,v in edges.items()):
        raise ValueError("数值曲线与编辑文档连接不一致")
    points = {p["id"]: p for p in dc["points"]}
    x0, y0, x1, y1 = doc["source"]["plot"]
    for p in ordered:
        dp = points[p["id"]]
        if not all(finite(p.get(k)) for k in ("frequency_pixel", "amplitude_pixel", "frequency_thz", "reconstructed_amplitude")):
            raise ValueError("存在缺失或非有限数值，未自动调整频率")
        if p["frequency_thz"] < 0 or p["reconstructed_amplitude"] < 0 and not numerical_zero(curve,p):
            raise ValueError("存在负频率或负幅值，未自动调整频率")
        if (dp[direction] != p["frequency_pixel"] or dp["y" if direction=="x" else "x"] != p["amplitude_pixel"]
                or not x0 <= dp["x"] <= x1 or not y0 <= dp["y"] <= y1):
            raise ValueError("编辑像素不一致或已超出图框")
        if not math.isclose(p["frequency_thz"], frequency(p["frequency_pixel"]), rel_tol=1e-12, abs_tol=abs(slope)*1e-9):
            raise ValueError("频率数值与当前像素标定不一致")
    groups = []
    for p in ordered:
        if groups and coincident(groups[-1][-1],p):
            groups[-1].append(p)
        else:
            groups.append([p])
    return groups, points, direction, axis, slope, frequency


def _repair_curve(curve, doc, timestamp, report):
    # 没有新人工动作时不进行第二轮优化，避免渐进累积和自动重做撤销。
    last = next((op for op in reversed(doc.get("operations", [])) if op.get("kind") != "auto-connect-exact-endpoints"), {})
    if last.get("kind") in {AUTO_KIND, UNDO_KIND}:
        return
    groups, document_points, direction, axis, slope, frequency = _inputs(curve, doc)
    if len(groups) < 2:
        return
    sign = 1 if slope > 0 else -1
    values = [sign*g[0]["frequency_pixel"] for g in groups]
    if all(b > a for a,b in zip(values,values[1:])):
        return
    blocks = _blocks(values)
    means = [total/count for _,_,total,count in blocks]
    bounds = doc["source"]["plot"]
    low,high = (bounds[0],bounds[2]) if direction=="x" else (bounds[1],bounds[3])
    low,high = sorted((sign*low, sign*high))
    step = max(MIN_STEP_PX, 64*math.ulp(max(1.,abs(low),abs(high))))
    zero_ids = set((doc.get("zero") or {}).get("pointIds",[]))
    changes, block_count = [], 0
    for bi,(start,end,total,count) in enumerate(blocks):
        if count == 1:
            continue
        mean = means[bi]
        center_low, center_high = -math.inf, math.inf
        offsets = [(j-(count-1)/2)*step for j in range(count)]
        locks = []
        for j,index in enumerate(range(start,end)):
            group=groups[index];value=values[index];f=group[0]["frequency_thz"]
            locked = index in {0,len(groups)-1} or f == 0 or any(p["id"] in zero_ids for p in group)
            locked = locked or curve["kind"] == "alpha2f" and f/abs(slope) <= 1
            locks.append(locked)
            radius = 0 if locked else MAX_SHIFT_PX
            center_low = max(center_low, max(low,value-radius)-offsets[j])
            center_high = min(center_high, min(high,value+radius)-offsets[j])
        # 原始邻点边界与拟合块分界同时约束；邻块拒绝也不能产生新的回折。
        if start:
            separator=(means[bi-1]+mean)/2
            center_low=max(center_low,max(values[start-1]+step,separator+step)-offsets[0])
        if end<len(groups):
            separator=(mean+means[bi+1])/2
            center_high=min(center_high,min(values[end]-step,separator-step)-offsets[-1])
        reason = None
        if center_low > center_high:
            reason = "消除该段回折需要超过0.5原图像素，或与固定点/相邻边界冲突"
        else:
            center=min(max(mean,center_low),center_high)
            candidates=[sign*(center+offset) for offset in offsets]
            # 固定点按原字节坐标保留，避免中心减加偏移造成ULP级漂移。
            candidates=[groups[start+j][0]["frequency_pixel"] if locks[j] else p for j,p in enumerate(candidates)]
            frequencies=[groups[start+j][0]["frequency_thz"] if locks[j] else frequency(p) for j,p in enumerate(candidates)]
            if (any(abs(p-groups[i][0]["frequency_pixel"])>MAX_SHIFT_PX for i,p in zip(range(start,end),candidates))
                    or not all(finite(f) and f>=0 for f in frequencies)
                    or any(b<=a for a,b in zip(frequencies,frequencies[1:]))
                    or start and frequencies[0]<=groups[start-1][0]["frequency_thz"]
                    or end<len(groups) and frequencies[-1]>=groups[end][0]["frequency_thz"]):
                reason = "数值精度或邻点约束不足以保持严格递增，原点保留"
        if reason:
            report["skipped"].append(dict(reason=reason,points=[location(curve,p["id"],p)
                                                               for p in (groups[start][0],groups[end-1][-1])]))
            continue
        block_count+=1
        for index,new_pixel,new_frequency in zip(range(start,end),candidates,frequencies):
            for p in groups[index]:
                if new_pixel != p["frequency_pixel"]:
                    changes.append((p,document_points[p["id"]],new_pixel,new_frequency))
    if not changes:
        return
    batch_id=uuid.uuid4().hex
    base=dict(batch_id=batch_id,direction=direction,frequency_calibration=axis)
    operations=[];chunk=[]
    for p,dp,new_pixel,_ in changes:
        entry=[p["id"],p["frequency_pixel"],new_pixel]
        candidate=json.dumps({**base,"changes":chunk+[entry]},separators=(",",":"))
        if len(candidate)>3500 and chunk:
            operations.append(dict(kind=AUTO_KIND,at=timestamp,detail=json.dumps({**base,"changes":chunk},separators=(",",":"))))
            chunk=[]
        chunk.append(entry)
    if chunk:
        operations.append(dict(kind=AUTO_KIND,at=timestamp,detail=json.dumps({**base,"changes":chunk},separators=(",",":"))))
    if len(doc.get("operations",[]))+len(operations)>5000 or len(json.dumps(doc))+len(json.dumps(operations))+len(changes)*64>3_990_000:
        report["skipped"].append(dict(reason="编辑历史容量不足，未写入自动修正",points=[]))
        return
    for p,dp,pixel,f in changes:
        p.update(frequency_pixel=pixel,frequency_thz=f,status=STATUS,manual=True)
        dp.update({direction:pixel,"status":STATUS,"manual":True})
    doc["operations"].extend(operations)
    report.update(new_point_count=len(changes),new_block_count=block_count)


def repair_frequencies(payload,kind,timestamp):
    reports=[]
    for curve in payload.get("curves",[]):
        if curve["kind"]!=kind:
            continue
        doc=payload.get("manual_documents",{}).get(curve["id"])
        if not doc:
            continue
        report=dict(curve_id=curve["id"],name=curve.get("projection") or "α²F",
                    new_point_count=0,new_block_count=0,points=[],point_count=0,max_shift_px=0.,skipped=[])
        try:
            _repair_curve(curve,doc,timestamp,report)
            report["points"]=_active_points(curve,doc)
            report["point_count"]=len(report["points"])
            report["max_shift_px"]=max((p["shift_px"] for p in report["points"]),default=0.)
        except (KeyError,TypeError,ValueError,ZeroDivisionError,OverflowError) as exc:
            report["skipped"].append(dict(reason=str(exc),points=[]))
        reports.append(report)
    return reports

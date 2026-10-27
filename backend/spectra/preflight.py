"""数值/边界预检查及有证据的表示修复；不构造曲线数值。"""
from __future__ import annotations

import json
import math
from .topology import build_graph, graph_parts, point_id, location, finite


def coincident(a, b):
    """只有显式相连、源像素和数值全相同才是同一样本的重复表示。"""
    return ((isinstance(a.get("joinTo"),str) and a["joinTo"] == b.get("id"))
            or (isinstance(b.get("joinTo"),str) and b["joinTo"] == a.get("id"))) and all(
        finite(a.get(k)) and a[k] == b.get(k)
        for k in ("frequency_pixel", "amplitude_pixel", "frequency_thz", "reconstructed_amplitude"))


def path_points(curve):
    nodes, edges, invalid = build_graph(curve)
    parts, cycles = graph_parts(edges)
    ends = [key for key in edges if len(edges[key]) == 1]
    if invalid or cycles or len(parts) != 1 or len(ends) != 2 or any(len(v) > 2 for v in edges.values()):
        return []
    ordered, seen, key = [], set(), ends[0]
    while key not in seen:
        seen.add(key)
        ordered.append(nodes[key])
        following = [p for p in edges[key] if p not in seen]
        if not following:
            break
        key = following[0]
    if all(finite(p.get("frequency_thz")) for p in (ordered[0], ordered[-1])) and ordered[0]["frequency_thz"] > ordered[-1]["frequency_thz"]:
        ordered.reverse()
    return ordered


def numerical_zero(curve, point):
    value = point.get("reconstructed_amplitude")
    axis = curve.get("axis_calibration",{}).get("amplitude",{})
    if value == 0:
        return True
    if finite(value) and finite(point.get("amplitude_pixel")) and axis:
        terms = (axis["slope"]*point["amplitude_pixel"],axis["intercept"])
        return abs(value) <= 8*sum(math.ulp(abs(v)) for v in terms)
    return False


def sample_issues(curve, document=None):
    issues, points = [], curve.get("points") or []
    def add(kind,message,pairs,meta=None):
        issue=dict(kind=kind,message=message,points=[location(curve,k,p) for k,p in pairs])
        if meta:issue["meta"]=meta
        issues.append(issue)
    finite_pairs=[]
    keys={id(p):point_id(curve,p,i) for i,p in enumerate(points)}
    for i,p in enumerate(points):
        key=point_id(curve,p,i); f,a=p.get("frequency_thz"),p.get("reconstructed_amplitude")
        if not finite(f) or not finite(a):
            add("nonfinite_sample","样本缺少有效频率或幅值，请对照原图补选或调整",[(key,p)])
        if finite(f):
            finite_pairs.append((key,p))
            if f<0:add("negative_frequency","频率为负，请核对频率轴或该点",[(key,p)])
        if finite(a) and a<0 and not numerical_zero(curve,p):
            add("negative_amplitude","幅值为负，请核对幅值零基线或该点",[(key,p)])
    ordered=path_points(curve)
    for a,b in zip(ordered,ordered[1:]):
        x,y=a.get("frequency_thz"),b.get("frequency_thz")
        if finite(x) and finite(y) and y<=x and not coincident(a,b):
            add("duplicate_frequency" if y==x else "frequency_backtrack",
                "相连点频率重复，无法作为单值谱积分" if y==x else "相连点频率回折，请对照原图调整连线或坐标",
                [(keys[id(a)],a),
                 (keys[id(b)],b)])
    if finite_pairs:
        key,first=min(finite_pairs,key=lambda pair:pair[1]["frequency_thz"])
        if abs(first["frequency_thz"]) > 1e-12*max(1.,max(p["frequency_thz"] for _,p in finite_pairs)):
            add("low_endpoint","实际低频端未到0频率，请核对原图真实边界",[(key,first)])
        elif curve["kind"]=="alpha2f" and finite(first.get("reconstructed_amplitude")) and not numerical_zero(curve,first):
            add("nonzero_zero","零频点幅值非零，当前分段线性积分发散；请核对原图，系统不会将幅值改零",[(key,first)])
        if document is not None:
            from .manual import zero_report
            if not zero_report(document)["complete"]:
                add("zero_confirmation","请核对原图零频线及曲线对应点，并在编辑器中明确确认",[(key,first)])
    return issues


def prepare_repairs(payload, kind, timestamp):
    """精确断端按哈希分组，片段并查集合并；所有点及坐标保持。"""
    repairs=[]
    for curve in payload.get("curves",[]):
        doc=payload.get("manual_documents",{}).get(curve["id"])
        if curve["kind"]!=kind or not doc or len(doc.get("operations",[]))>=4999:
            continue
        try:
            nodes,edges,invalid=build_graph(curve)
        except ValueError:
            continue
        if invalid:continue
        parts,_=graph_parts(edges)
        document_points={p["id"]:p for p in doc["curves"][0]["points"]}
        document_size=len(json.dumps(doc))
        blocked=set();block_all=False
        for op in doc.get("operations",[]):
            if op.get("kind")!="undo-auto-connect":continue
            try:
                blocked.update(frozenset((e["from_id"],e["to_id"])) for e in json.loads(op["detail"])["edges"])
            except (KeyError,TypeError,ValueError):
                block_all=True
        if block_all:continue
        parent=list(range(len(parts)));ranges={};groups={}
        def root(i):
            while parent[i]!=i:
                parent[i]=parent[parent[i]];i=parent[i]
            return i
        for index,part in enumerate(parts):
            ends=[k for k in part if len(edges[k])<=1]
            if len(part)>1 and (len(ends)!=2 or any(len(edges[k])>2 for k in part)):
                continue
            start=ends[0] if ends else None
            if start is None:continue
            seq=[];seen=set();key=start
            while key not in seen:
                seen.add(key);seq.append(nodes[key])
                following=[k for k in edges[key] if k not in seen]
                if not following:break
                key=following[0]
            if len(seen)!=len(part) or not all(finite(p.get("frequency_thz")) and finite(p.get("reconstructed_amplitude")) for p in seq):
                continue
            fs=[p["frequency_thz"] for p in seq]
            if not (all(b>a for a,b in zip(fs,fs[1:])) or all(b<a for a,b in zip(fs,fs[1:]))):continue
            ranges[index]=[min(fs),max(fs)]
            for key in ends:
                p=nodes[key];loc=location(curve,key,p);dp=document_points.get(key)
                if not dp or not all(finite(p.get(k)) for k in ("frequency_pixel","amplitude_pixel")):continue
                if dp["x"]!=loc["x"] or dp["y"]!=loc["y"]:continue
                group=(loc["x"],loc["y"],p["frequency_thz"],p["reconstructed_amplitude"])
                groups.setdefault(group,[]).append((index,key))
        for group,candidates in groups.items():
            if len(candidates)!=2 or len(doc["operations"])>=4999:continue
            (i,a),(j,b)=candidates
            if frozenset((a,b)) in blocked:continue
            i,j=root(i),root(j)
            if i==j or i not in ranges or j not in ranges:continue
            f=group[2];lo,hi=min(ranges[i][0],ranges[j][0]),max(ranges[i][1],ranges[j][1])
            if hi<=lo or not ((ranges[i][1]==f==ranges[j][0]) or (ranges[j][1]==f==ranges[i][0])):continue
            if nodes[a].get("joinTo"):
                a,b=b,a
            if nodes[a].get("joinTo"):continue
            detail=dict(from_id=a,to_id=b)
            operation=dict(kind="auto-connect-exact-endpoints",at=timestamp,detail=json.dumps(detail,separators=(",",":")))
            addition=len(json.dumps(operation))+len(json.dumps(b))+128
            if document_size+addition>3_990_000:continue
            document_size+=addition
            nodes[a]["joinTo"]=b;document_points[a]["joinTo"]=b
            parent[j]=i;ranges[i]=[lo,hi]
            doc["operations"].append(operation)
            repairs.append(dict(curve_id=curve["id"],message="已自动连接像素与数值完全重合的唯一断端，全部点保留",
                                points=[location(curve,a,nodes[a]),location(curve,b,nodes[b])]))
    return repairs

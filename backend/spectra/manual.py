"""人工谱修订：服务器生成编辑输入，验证像素后创建不可变运行。"""
from __future__ import annotations
import copy
import json
import math
import uuid
from datetime import datetime, timezone
from sqlalchemy import select
from backend import models
from backend.services import spectra as service
from backend.spectra.contracts import FREQUENCY_FACTORS, fingerprint, state_signature

VERSION = "spectra-manual-v1"
KINDS = {"alpha2f", "phonon_dos"}


def require(condition, message, status=422):
    if not condition:
        service.fail("spectra_manual_invalid", message, status)


def current(session, ctx, identity, expected=None, base_run=None, *, allow_state_changed=False):
    require(ctx.get("can_edit"), "没有编辑谱数据的权限", 403)
    row = session.scalar(select(models.SpectrumCollection).where(models.SpectrumCollection.id == identity)
                         .with_for_update().execution_options(populate_existing=True))
    require(row and row.target == ctx["target"] and row.target_id == ctx["target_id"], "谱集合不属于当前目标", 404)
    if expected is not None:
        service.assert_version(row.version, expected)
    if base_run is not None:
        service.assert_version(row.current_run_id, base_run)
    if ctx["target"] == "paper":
        service.assert_version(row.paper_revision, ctx["paper_revision"])
    state = next((s for s in ctx["states"] if s["state_key"] == row.state_key), None)
    require(state is not None, "材料归属已不存在，请返回材料表单核对", 409)
    require(allow_state_changed or row.state_signature == state_signature(state), "材料状态已变化，请先核对材料条件后继续编辑", 409)
    require("files" not in ctx or row.source_json.get("source_sha256") in {f.get("sha256") for f in ctx["files"]}, "来源文件已变化", 409)
    run = session.get(models.SpectrumRun, row.current_run_id)
    require(run and run.status in {"succeeded", "needs_review"} and (run.result_json or {}).get("curves"), "当前运行尚无可编辑谱数据", 409)
    return row, run, state


def assert_latest(session, ctx, row, kind):
    family = {"alpha2f", "cumulative_lambda"} if kind == "alpha2f" else {kind}
    items = [i for i in service.listing(session, ctx)["items"] if i["state_key"] == row.state_key
             and any(c["kind"] in family for c in i["result"].get("curves", []))]
    latest = max(items, key=lambda i:(i.get("recorded_at", ""), i["id"]), default=None)
    require(latest and latest["id"] == row.id, "这是历史谱集合，请打开当前版本编辑", 409)


def axis_from_result(axis, bounds, unit):
    require(axis and math.isfinite(axis.get("slope", float("nan"))) and axis["slope"] != 0, "缺少有效线性标定")
    return dict(pixels=list(bounds), values=[axis["slope"]*p+axis["intercept"] for p in bounds], unit=unit)


def editor_document(row, run, curve):
    stored = (run.result_json or {}).get("manual_documents", {}).get(curve["id"])
    if stored:
        doc=copy.deepcopy(stored)
        # 返修复制会生成新集合身份，保留点和来源像素，但编辑文档不能仍指向旧集合。
        doc["id"]=f"{row.id}:{curve['id']}"
        doc["source"]["id"]=row.id
        if doc.get("recognizedAxes"):
            doc["recognizedAxes"]["sourceId"]=row.id
        return doc
    source = row.source_json
    size = source.get("size_px") or []
    require(len(size) == 2 and all(isinstance(v, int) and v > 0 for v in size), "缺少原图尺寸，不能安全编辑")
    width, height = size
    spec = next((c for c in (run.result_json.get("calibration") or run.calibration_json or {}).get("curves", []) if c["id"] == curve["id"]), {})
    direction = curve.get("frequency_direction")
    require(direction in {"x", "y"} and len(curve.get("roi") or []) == 4, "缺少图框或轴方向")
    plot = list(curve["roi"])
    faxis = curve.get("axis_calibration", {}).get("frequency")
    require(faxis and faxis.get("slope"), "缺少频率标定")
    zero = -faxis["intercept"]/faxis["slope"]
    lo, hi, extent = (1, 3, height) if direction == "y" else (0, 2, width)
    if 0 <= zero < extent:
        plot[lo], plot[hi] = min(plot[lo], zero), max(plot[hi], zero)
    require(0 <= plot[0] < plot[2] < width and 0 <= plot[1] < plot[3] < height, "图框不在来源图片内")
    crop = curve.get("display_bbox") or [max(0,plot[0]-8),max(0,plot[1]-8),min(width-1,plot[2]+12),min(height-1,plot[3]+24)]
    require(len(crop) == 4 and 0 <= crop[0] <= plot[0] < plot[2] <= crop[2] < width
            and 0 <= crop[1] <= plot[1] < plot[3] <= crop[3] < height, "来源裁切范围无效")
    fb = [plot[lo], plot[hi]]
    ab = [plot[0],plot[2]] if direction == "y" else [plot[3],plot[1]]
    unknown = curve["kind"] == "alpha2f" and not spec.get("amplitude_evidence") or curve.get("unit") in {"pixel", "unknown"}
    amp = dict(pixels=ab,values=[0,abs(ab[1]-ab[0])],unit="pixel") if unknown else axis_from_result(curve.get("axis_calibration", {}).get("amplitude"), ab, curve["unit"])
    points, segment, interrupted = [], 0, True
    for i, p in enumerate(curve.get("points", [])):
        fp, ap = p.get("frequency_pixel"), p.get("amplitude_pixel")
        if ap is None and p.get("reconstructed_amplitude") is not None:
            a = curve.get("axis_calibration", {}).get("amplitude") or {}
            if a.get("slope"):
                ap = (p["reconstructed_amplitude"]-a["intercept"])/a["slope"]
        if fp is None or ap is None:
            interrupted = True
            continue
        if interrupted:
            segment += 1
        x, y = (ap,fp) if direction == "y" else (fp,ap)
        if not (plot[0] <= x <= plot[2] and plot[1] <= y <= plot[3]):
            interrupted = True
            continue
        points.append(dict(id=p.get("id") or f"{curve['id']}:p{i}", x=x, y=y, segment=str(segment),
                           breakBefore=interrupted, status=p.get("status", "observed"), manual=bool(p.get("manual"))))
        interrupted = False
    image_hash = (source.get("image") or {}).get("sha256") or source.get("source_sha256") or row.source_key
    reference = dict(sourceId=row.id, sourceSha256=image_hash, direction=direction,
                     frequencyUnit=spec.get("frequency_unit", "THz"), frequencyTicks=spec.get("frequency_ticks", []), lambdaTicks=[])
    # 未确认幅值不能把旧标定候选直接画成 α²F 幅值或擅自认定为 λ。
    return dict(schemaVersion=1,id=f"{row.id}:{curve['id']}",title=curve.get("projection") or ("α²F 谱函数" if curve["kind"] == "alpha2f" else "声子 DOS"),
                description="人工修订保存到谱历史运行；不自动科学采纳。",
                source=dict(id=row.id,sha256=image_hash,image="",width=width,height=height,plot=plot,
                            viewport=[crop[0],crop[1],crop[2]-crop[0],crop[3]-crop[1]]),
                calibration=dict(direction=direction,frequency=axis_from_result(faxis,fb,"THz"),amplitude=amp,
                                 amplitudeEvidence=spec.get("amplitude_evidence") or ""),
                curves=[dict(id=curve["id"],name=curve.get("projection") or "α²F",color={"La":"#6256dd","Sc":"#d84491","H":"#07996c"}.get(curve.get("projection"),"#e9526b"),points=points,pathOrdered=True)],
                zero=None,operations=[],recognizedAxes=reference)


def documents(session, ctx, row, run, kind):
    require(kind in KINDS, "只支持α²F和声子DOS编辑")
    assert_latest(session, ctx, row, kind)
    curves = [c for c in run.result_json.get("curves", []) if c["kind"] == kind]
    require(curves, "当前谱类型没有可编辑曲线")
    return dict(documents=[editor_document(row,run,c) for c in curves], base_run_id=run.id,
                collection_version=row.version, version=ctx["version"])


def finite(value):
    return isinstance(value, (int,float)) and not isinstance(value,bool) and math.isfinite(value)


def checked_document(body, seed):
    try:
        require(len(json.dumps(body,allow_nan=False)) <= 4_000_000, "编辑数据超过4MB限制")
        require(set(body) <= set(seed), "含不支持的编辑字段")
        require({"schemaVersion","id","title","description","source","calibration","curves","zero","operations"} <= set(body), "编辑文档缺少必要字段")
        require(body["schemaVersion"] == 1 and body["id"] == seed["id"], "编辑身份不匹配")
        source = {**body["source"], "image":""}
        require(source == seed["source"], "来源图片或图框已变化，不能替换来源")
        cal = body["calibration"]
        require(set(cal) == {"direction","frequency","amplitude","amplitudeEvidence"} and cal["direction"] in {"x","y"}, "标定字段无效")
        for name in ("frequency","amplitude"):
            axis = cal[name]
            require(set(axis) == {"pixels","values","unit"}, "标定字段无效")
            for field in ("pixels","values"):
                values = axis[field]
                require(isinstance(values,list) and len(values)==2 and all(finite(v) for v in values) and abs(values[1]-values[0])>1e-9, "标定两点必须有限且不退化")
            dimension = cal["direction"] if name == "frequency" else ("x" if cal["direction"]=="y" else "y")
            require(all(0 <= p < source["width" if dimension=="x" else "height"] for p in axis["pixels"]), "刻度像素超出原图")
            require(isinstance(axis["unit"],str) and 0 < len(axis["unit"]) <= 96, "单位无效")
            slope=(axis["values"][1]-axis["values"][0])/(axis["pixels"][1]-axis["pixels"][0])
            intercept=axis["values"][0]-slope*axis["pixels"][0]
            require(finite(slope) and slope != 0 and finite(intercept), "标定换算系数溢出或退化")
        require(cal["frequency"]["unit"] in FREQUENCY_FACTORS, "频率单位不支持")
        require(isinstance(cal["amplitudeEvidence"],str) and len(cal["amplitudeEvidence"]) <= 4000, "幅值依据过长")
        require(cal["amplitude"]["unit"] in {seed["calibration"]["amplitude"]["unit"],"pixel","dimensionless","modes/THz","unknown"}, "幅值单位不支持")
        require(cal["amplitude"] == seed["calibration"]["amplitude"] or cal["amplitude"]["unit"] in {"pixel","unknown"}
                or bool(cal["amplitudeEvidence"].strip()), "物理幅值标定修改必须提供原图依据")
        require(len(body["curves"]) == 1, "每次只能保存一条曲线")
        curve, original = body["curves"][0], seed["curves"][0]
        require(set(curve) <= {"id","name","color","points","pathOrdered"} and curve.get("pathOrdered") is True, "曲线字段或描线顺序标记无效")
        require(all(curve[k] == original[k] for k in ("id","name","color")), "曲线身份不匹配")
        require(isinstance(curve["points"],list) and len(curve["points"]) <= 20000, "数据点超过20000个")
        require(all(isinstance(p,dict) for p in curve["points"]), "点结构无效")
        ids=set();x0,y0,x1,y1=source["plot"]
        curve_ids={p.get("id") for p in curve["points"]}
        for p in curve["points"]:
            require(set(p) <= {"id","x","y","segment","status","manual","breakBefore","connectTo","joinTo"}, "点含不支持字段")
            require(isinstance(p["id"],str) and 0<len(p["id"])<=160 and p["id"] not in ids, "点身份重复或无效")
            require("connectTo" not in p or isinstance(p["connectTo"],str) and p["connectTo"] in ids, "描线前驱必须属于当前曲线且位于该点之前")
            require("joinTo" not in p or isinstance(p["joinTo"],str) and p["joinTo"] != p["id"] and p["joinTo"] in curve_ids, "吸附目标必须是同曲线其他已有点")
            ids.add(p["id"])
            require(finite(p["x"]) and finite(p["y"]) and x0<=p["x"]<=x1 and y0<=p["y"]<=y1, "点像素超出图框或不是有限值")
            require(isinstance(p["segment"],str) and len(p["segment"])<=160 and isinstance(p["status"],str) and len(p["status"])<=96, "点来源字段无效")
            require(all(k not in p or isinstance(p[k],bool) for k in ("manual","breakBefore")), "连线标记无效")
        edges=set()
        for i,p in enumerate(curve["points"]):
            previous=curve["points"][i-1] if i else None
            parent=p.get("connectTo")
            if parent is None and previous:
                connected=(not p["breakBefore"]) if "breakBefore" in p else previous["segment"]==p["segment"] or previous.get("manual") or p.get("manual")
                if connected: parent=previous["id"]
            if parent: edges.add(tuple(sorted((p["id"],parent))))
        for p in curve["points"]:
            if p.get("joinTo"):
                edge=tuple(sorted((p["id"],p["joinTo"])))
                require(edge not in edges, "吸附连接已存在，不能重复添加")
                edges.add(edge)
        zero=body.get("zero")
        if zero is not None:
            require(set(zero)=={"pixel","pointIds"} and finite(zero["pixel"]) and isinstance(zero["pointIds"],list)
                    and set(zero["pointIds"])<=ids, "零频记录无效")
            require(abs(axis_value(cal["frequency"],zero["pixel"])) < 1e-6, "零频位置与标定不一致")
            low,high=(x0,x1) if cal["direction"]=="x" else (y0,y1)
            require(low <= zero["pixel"] <= high, "零频标记不在图框内")
        require(isinstance(body["operations"],list) and len(body["operations"]) <= 5000, "操作记录过多")
        for op in body["operations"]:
            require(set(op)=={"kind","at","detail"} and all(isinstance(v,str) and len(v)<=4000 for v in op.values()), "操作记录无效")
        result=copy.deepcopy(body)
        result.update(source=seed["source"],title=seed["title"],description=seed["description"],recognizedAxes=seed.get("recognizedAxes"))
        result["curves"][0]["pathOrdered"]=True
        return result
    except (KeyError,TypeError,ValueError,OverflowError):
        service.fail("spectra_manual_invalid", "人工修订结构或数值无效",422)


def axis_value(axis,pixel):
    return axis["values"][0]+(pixel-axis["pixels"][0])*(axis["values"][1]-axis["values"][0])/(axis["pixels"][1]-axis["pixels"][0])


def zero_report(doc):
    axis=doc["calibration"]["frequency"];slope=(axis["values"][1]-axis["values"][0])/(axis["pixels"][1]-axis["pixels"][0])
    pixel=axis["pixels"][0]-axis["values"][0]/slope
    direction=doc["calibration"]["direction"];lo,hi=(0,2) if direction=="x" else (1,3)
    boundary="invalid" if not doc["source"]["plot"][lo]<=pixel<=doc["source"]["plot"][hi] else "missing" if doc["zero"] is None else "confirmed"
    curve=doc["curves"][0];ids=set((doc["zero"] or {}).get("pointIds",[]));nearest=None;candidate=None;confirmed=None
    for p in curve["points"]:
        distance=abs(p[direction]-pixel)
        if nearest is None or distance<nearest["distancePx"]:
            nearest=dict(id=p["id"],frequency=axis_value(axis,p[direction])*FREQUENCY_FACTORS[axis["unit"]],distancePx=distance)
        if distance<=1e-4:
            candidate=candidate or p["id"]
            if p["id"] in ids:confirmed=confirmed or p["id"]
    status="needs_boundary" if boundary!="confirmed" else "complete" if confirmed else "needs_confirmation" if candidate else "missing_point"
    return dict(complete=status=="complete",boundary=boundary,zeroPixel=pixel,completedCount=int(status=="complete"),
                curves=[dict(id=curve["id"],name=curve["name"],status=status,pointId=confirmed or candidate,nearest=nearest)])


def invalidate_derived(payload, reason):
    checks={key:zero_report(value) for key,value in payload.get("manual_documents",{}).items()}
    for c in payload["curves"]:
        if c["kind"] in KINDS and c["id"] not in checks:
            checks[c["id"]]=dict(complete=False,boundary="missing",zeroPixel=None,completedCount=0,
                curves=[dict(id=c["id"],name=c.get("projection") or "α²F",status="needs_boundary",pointId=None,nearest=None)])
    payload["quality"]={"curves":{c["id"]:{"total_points":len(c["points"])} for c in payload["curves"]},
        "integrals":{"raw":{"status":"unavailable","reason":reason}},"comparisons":{},
        "dos_mode_integral":{"status":"unavailable","reason":reason},"manual_zero_checks":checks,"limitations":[reason]}
    payload["candidates"]={};payload["failures"]=[];payload["status"]="needs_review"


def save(session,ctx,row,run,document,user):
    require(isinstance(document.get("curves"),list) and len(document["curves"])==1 and isinstance(document["curves"][0],dict), "每次须提交一条曲线")
    cid=document["curves"][0].get("id")
    original=next((c for c in run.result_json.get("curves",[]) if c["id"]==cid and c["kind"] in KINDS),None)
    require(original, "不允许增加、替换其他谱类型或曲线身份")
    assert_latest(session,ctx,row,original["kind"])
    seed=editor_document(row,run,original);doc=checked_document(document,seed)
    cal=doc["calibration"];direction=cal["direction"];factor=FREQUENCY_FACTORS[cal["frequency"]["unit"]]
    axes={}
    for name in ("frequency","amplitude"):
        a=cal[name];slope=(a["values"][1]-a["values"][0])/(a["pixels"][1]-a["pixels"][0])
        scale=factor if name=="frequency" else 1.
        axes[name]=dict(slope=slope*scale,intercept=(a["values"][0]-slope*a["pixels"][0])*scale,max_tick_residual=0.)
        require(all(finite(v) for v in axes[name].values()), "规范单位换算溢出")
    numeric=[]
    originals={p.get("id") or f"{cid}:p{i}":p for i,p in enumerate(original["points"])}
    same_cal=cal==seed["calibration"]
    for p in doc["curves"][0]["points"]:
        fp,ap=p[direction],p["x" if direction=="y" else "y"]
        old=originals.get(p["id"],{})
        amplitude_value=axis_value(cal["amplitude"],ap)
        unchanged=(same_cal and original.get("unit")==cal["amplitude"]["unit"] and old.get("frequency_pixel")==fp
                   and old.get("amplitude_pixel")==ap and old.get("reconstructed_amplitude") is not None
                   and abs(old["reconstructed_amplitude"]-amplitude_value)<1e-9)
        numeric.append(dict(id=p["id"],frequency_pixel=fp,amplitude_pixel=ap,
            frequency_thz=axis_value(cal["frequency"],fp)*factor,reconstructed_amplitude=amplitude_value,
            observed_amplitude=old.get("observed_amplitude") if unchanged else None,
            status=old.get("status","manual_adjusted") if unchanged else "manual_adjusted", manual=not unchanged,
            segment=p["segment"],breakBefore=p.get("breakBefore",False),
            **({"connectTo":p["connectTo"]} if "connectTo" in p else {}),
            **({"joinTo":p["joinTo"]} if "joinTo" in p else {})))
    require(all(finite(p[k]) for p in numeric for k in ("frequency_thz","reconstructed_amplitude")), "换算结果溢出")
    payload=copy.deepcopy(run.result_json)
    changed={**original,"points":numeric,"frequency_direction":direction,"axis_calibration":axes,"unit":cal["amplitude"]["unit"],
             "source_frequency_unit":cal["frequency"]["unit"],"manual_trace":True,"clipped_frequencies_thz":[]}
    payload["curves"]=[changed if c["id"]==cid else c for c in payload["curves"]]
    payload.setdefault("manual_documents",{})[cid]=doc
    reason="人工修订已保存，旧积分已失效；请点击“重新计算”检查并计算当前谱。"
    invalidate_derived(payload,reason)
    payload["algorithm_version"]=VERSION
    payload["manual_provenance"]=dict(base_run_id=run.id,author_id=user.id,curve_id=cid,created_at=datetime.now(timezone.utc).isoformat())
    fresh=models.SpectrumRun(id=uuid.uuid4().hex,collection_id=row.id,
        input_hash=fingerprint(dict(parent=run.id,document=doc,actor=user.id)),algorithm_version=VERSION,
        status="succeeded",calibration_json=copy.deepcopy(run.calibration_json),result_json=payload,completed_at=datetime.now(timezone.utc))
    session.add(fresh);session.flush()
    row.current_run_id=fresh.id;row.version+=1;row.review_json={}
    return fresh


def revalidate(session, ctx, row, run, state, kind, user):
    require(kind in KINDS, "只支持α²F和声子DOS材料核对")
    assert_latest(session, ctx, row, kind)
    require(any(c["kind"] == kind for c in run.result_json["curves"]), "当前谱类型没有数据")
    signature = state_signature(state)
    require(row.state_signature != signature, "当前材料条件有效，无需重复核对", 409)
    payload = copy.deepcopy(run.result_json)
    now = datetime.now(timezone.utc)
    payload["state_revalidation"] = dict(base_run_id=run.id, previous_state_signature=row.state_signature,
        state_signature=signature, author_id=user.id, confirmed_at=now.isoformat(),
        material_summary={k:state.get(k) for k in (
            "state_key", "material", "material_name", "pressure_value_gpa", "pressure_min_gpa", "pressure_max_gpa",
            "reported_space_group_symbol", "temperature_value_k")})
    invalidate_derived(payload, "材料条件已重新核对；旧积分已失效，请点击重新计算。")
    version = "spectra-state-revalidation-v1"
    payload["algorithm_version"] = version
    fresh = models.SpectrumRun(id=uuid.uuid4().hex, collection_id=row.id,
        input_hash=fingerprint(dict(parent=run.id, state=signature, actor=user.id, algorithm=version)),
        algorithm_version=version, status="succeeded", calibration_json=copy.deepcopy(run.calibration_json),
        result_json=payload, completed_at=now)
    session.add(fresh)
    session.flush()
    row.state_signature = signature
    row.current_run_id = fresh.id
    row.version += 1
    row.review_json = {}
    return fresh

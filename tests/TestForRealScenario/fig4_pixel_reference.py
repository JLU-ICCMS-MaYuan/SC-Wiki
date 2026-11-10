"""Peng2017 Fig.4测试参照：原图刻度人工核对、像素测量；不用于生产填值。"""
from pathlib import Path
import hashlib,io,re
import numpy as np
from PIL import Image
import pymupdf

PDF_SHA="bf0725bea058339b814489fe213ec8285a0fca01eb5143da95254330eea06846"
MATERIALS=["ScH6","ScH9","YH6","YH9","YH10","LaH6","LaH9","CeH9","CeH10","PrH9"]
PRESSURES=[300,400,120,150,400,100,50,100,200,100]
# 原图879×632中逐一核对的印刷刻度/基线；没有使用正文结果反推轴。
AXES={"dos_fermi":[(25,.04),(114,.02),(202,0)],"lambda_ep":[(241,4),(316,2),(392,0)],
      "tc":[(430,300),(481,200),(532,100),(583,0)]}
BASELINES={"dos_fermi":202,"lambda_ep":392,"tc":583}


def mask(rgb,color):
    r,g,b=rgb[...,0],rgb[...,1],rgb[...,2]
    if color=="red":return (r>180)&(g<90)&(b<90)
    if color=="blue":return (b>180)&(r<90)&(g<90)
    if color=="green":return (g>180)&(r<90)&(b<90)
    return (b>80)&(r<90)&(g<90)


def reference(pdf_path):
    raw=Path(pdf_path).read_bytes()
    assert hashlib.sha256(raw).hexdigest()==PDF_SHA
    with pymupdf.open(stream=raw,filetype="pdf") as pdf:
        info=max(pdf[3].get_image_info(xrefs=True),key=lambda i:i["width"]*i["height"])
        bitmap=pdf.extract_image(info["xref"])["image"]
    image=np.asarray(Image.open(io.BytesIO(bitmap)).convert("RGB"))
    assert image.shape[:2]==(632,879)
    data={"pdf_sha256":PDF_SHA,"native_image_sha256":hashlib.sha256(bitmap).hexdigest(),
          "native_image_bbox_page":list(info["bbox"]),"image_size":[879,632],"items":[],"unreadable":["PrH9 Tc both series"],
          "tolerance_basis":"3个原始位图像素，覆盖刻度定位、抗锯齿柱边及图像采样各1像素；与模型自报精度无关"}
    for quantity,colors in [("dos_fermi",[("red",None)]),("lambda_ep",[("blue",None)]),("tc",[("green",.1),("navy",.13)])]:
        ticks=[]
        for approximate,value in AXES[quantity]:
            profile=np.all(image[max(0,approximate-3):approximate+4,145:153]<128,axis=2).sum(axis=1)
            rows=np.flatnonzero(profile==profile.max())+approximate-3
            ticks.append((float(np.mean(rows)),value))
        slope,intercept=np.polyfit([x for x,y in ticks],[y for x,y in ticks],1)
        residual=max(abs(slope*x+intercept-y) for x,y in ticks)
        baseline=BASELINES[quantity]
        for color,mu in colors:
            foreground=mask(image[baseline-3],color)
            xs=np.flatnonzero(foreground)
            spans=[g for g in np.split(xs,np.flatnonzero(np.diff(xs)>1)+1) if len(g)>=3]
            expected=9 if quantity=="tc" else 10
            assert len(spans)==expected,(quantity,color,[(g[0],g[-1]) for g in spans])
            low=0 if quantity=="dos_fermi" else 204 if quantity=="lambda_ep" else 394
            for material,pressure,span in zip(MATERIALS,PRESSURES,spans):
                x=int(np.median(span));ys=np.flatnonzero(mask(image[low:baseline,x],color))+low
                assert len(ys)
                groups=np.split(ys,np.flatnonzero(np.diff(ys)>5)+1)
                connected=[group for group in groups if group[-1]>=baseline-4]
                assert len(connected)==1,(quantity,material,"基线连接柱不唯一")
                # 图例色块与真实柱之间有空白，不能取同列最上方的图例边缘。
                top=int(connected[0][0])
                data["items"].append({"quantity":quantity,"material":material,"pressure":pressure,"mu_star":mu,
                    "x_span":[int(span[0]),int(span[-1])],"y_top":top,"value":float(slope*top+intercept),
                    "tolerance":float(abs(slope)*3+residual),"ticks":ticks})
    return data


def unit_ok(quantity,unit):
    import unicodedata
    text=unicodedata.normalize("NFKC",str(unit or "")).lower().replace("angstrom","å").replace("states","state")
    text=text.replace("−","-")
    text=re.sub(r"[\s(){}^*·]","",text)
    if quantity=="dos_fermi":return text in {"state/ev/å3","state/evå3","state/eva3","state/ev/a3","stateev-1å-3","stateev-1a-3"}
    if quantity=="tc":return text in {"k","kelvin"}
    return text in {"","1","dimensionless","unitless"}


def validate(facts,expected):
    issues=[];seen=set();bykey={(v["quantity"],v["material"],v["mu_star"]):v for v in expected["items"]}
    bbox=expected["native_image_bbox_page"];width,height=expected["image_size"]
    digits=str.maketrans("₀₁₂₃₄₅₆₇₈₉","0123456789")
    for f in facts:
        p=f["point"];material=re.sub(r"[^A-Za-z0-9]","",p["material"].translate(digits))
        key=(f["quantity"],material,p.get("mu_star") if f["quantity"]=="tc" else None)
        if key not in bykey:issues.append({"code":"unexpected_or_unreadable_point","key":key});continue
        target=bykey[key]
        if not unit_ok(f["quantity"],f.get("unit")):issues.append({"code":"unit_mismatch","key":key,"unit":f.get("unit")})
        if key in seen:issues.append({"code":"duplicate","key":key})
        seen.add(key)
        if p.get("pressure_value_gpa")!=target["pressure"]:issues.append({"code":"pressure_mismatch","key":key})
        crop=f["crop_bbox"];page_x=crop[0]+p["x"]/1000*(crop[2]-crop[0])
        native_x=(page_x-bbox[0])*width/(bbox[2]-bbox[0])
        if not target["x_span"][0]-1<=native_x<=target["x_span"][1]+1:
            issues.append({"code":"wrong_bar_identity","key":key,"native_x":native_x,"expected_span":target["x_span"]})
        value=f.get("calculated_value",f["value_number"])
        if abs(value-target["value"])>target["tolerance"]:
            issues.append({"code":"value_mismatch","key":key,"value":value,"expected":target["value"],"tolerance":target["tolerance"]})
    issues.extend({"code":"missing","key":key} for key in bykey.keys()-seen)
    return issues


def validate_form_values(states,expected,fact_blocks):
    """按真实所有权展开Tc共同参数，核验ScH6四字段及来源/约数；不新增表单字段。"""
    from backend.ingest.tc_contexts import map_draft
    targets={(x["quantity"],x["mu_star"]):x for x in expected["items"] if x["material"]=="ScH6"}
    allowed={}
    for block in fact_blocks:
        f=block.metadata.get("chart_reading")
        if f and f["point"]["material"]=="ScH6":
            key=(f["quantity"],f["point"].get("mu_star") if f["quantity"]=="tc" else None)
            allowed.setdefault(key,set()).add(block.block_id)
    found={};issues=[]
    def number(value):
        return value.get("value_number",value.get("value")) if isinstance(value,dict) else value
    def add(key,record):
        if key not in targets:return
        value=number(record)
        if not unit_ok(key[0],record.get("canonical_unit") or record.get("unit_raw")):issues.append({"code":"form_unit_mismatch","key":key})
        if value is None or abs(value-targets[key]["value"])>targets[key]["tolerance"]:
            issues.append({"code":"form_value_mismatch","key":key,"value":value})
        if record.get("uncertainty") is not None:issues.append({"code":"graph_precision_as_measurement_error","key":key})
        if not any(mark in str(record.get("value_raw","")).lower() for mark in ["~","≈","approx"]):
            issues.append({"code":"approximate_qualifier_lost","key":key})
        refs={e.get("block_id") or e.get("quote_id") for e in record.get("evidences",[])}
        if not refs & allowed.get(key,set()):issues.append({"code":"original_graph_source_lost","key":key})
        found.setdefault(key,[]).append(value)
    for state in map_draft({"material_states":states})["material_states"]:
        if state.get("material")!="ScH6":continue
        if state.get("pressure_value_gpa")!=300:issues.append({"code":"form_pressure_mismatch"})
        for module in state.get("property_modules",[]):
            for record in module.get("records",[]):
                params=(record.get("payload") or {}).get("parameters") or {}
                code=record.get("property_code")
                if code=="tc":
                    add(("tc",number(params.get("mu_star"))),record)
                    if isinstance(params.get("lambda_ep"),dict):add(("lambda_ep",None),params["lambda_ep"])
                elif code=="dos_fermi":add(("dos_fermi",None),record)
    for key in targets:
        if key not in found:issues.append({"code":"form_missing","key":key})
        elif key[0]!="lambda_ep" and len(found[key])!=1:issues.append({"code":"form_duplicate","key":key})
    return issues

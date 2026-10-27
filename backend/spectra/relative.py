"""相对像素独立ωlog与论文λ归一化；任何偏差都不作操作门槛。"""
from __future__ import annotations

import copy
from .digitize import spectral_integrals
from .samples import connected_samples
from .topology import finite

METHOD = "alpha2f-relative-v1"


def unavailable(reason):
    return dict(status="unavailable",reason=str(reason))


def pixel_curve(payload,curve):
    """使用当前幅值零基线，舍弃旧刻度倍率；绝不把全局坐标当幅值。"""
    result=copy.deepcopy(curve)
    doc=payload.get("manual_documents",{}).get(curve["id"])
    axis=curve.get("axis_calibration",{}).get("amplitude") or {}
    if doc:
        a=doc["calibration"]["amplitude"]
        slope=(a["values"][1]-a["values"][0])/(a["pixels"][1]-a["pixels"][0])
        axis=dict(slope=slope,intercept=a["values"][0]-slope*a["pixels"][0])
    if finite(axis.get("slope")) and axis["slope"]!=0 and finite(axis.get("intercept")):
        baseline=-axis["intercept"]/axis["slope"]
        if not finite(baseline):raise ValueError("当前幅值零基线无效")
        sign=1 if axis["slope"]>0 else -1
        for point in result["points"]:
            pixel=point.get("amplitude_pixel")
            if not finite(pixel) and finite(point.get("reconstructed_amplitude")):
                pixel=(point["reconstructed_amplitude"]-axis["intercept"])/axis["slope"]
            point["amplitude_pixel"]=pixel
            point["reconstructed_amplitude"]=sign*(pixel-baseline) if finite(pixel) else None
        result["unit"]="pixel"
        result.setdefault("axis_calibration",{})["amplitude"]=dict(slope=sign,intercept=-sign*baseline)
        return result,dict(kind="source_pixels",baseline_pixel=baseline,direction=sign)
    if curve.get("unit")=="pixel":
        return result,dict(kind="stored_pixels",baseline_pixel=None,direction=None)
    # 旧数值谱可独立提供谱形平均，但缺失像素换算不能声称给出了每像素C。
    return result,dict(kind="stored_relative_values",baseline_pixel=None,direction=None)


def omega_comparison(value,reference,reason=None):
    ref=reference or {}
    paper=ref.get("value")
    base=dict(reference=paper if finite(paper) else None,source=ref.get("source"),value=value,
              absolute_difference=None,relative_difference_pct=None,signed_difference=None)
    if not finite(paper) or not ref.get("source") or not ref.get("same_conditions"):
        return dict(**base,**unavailable(reason or "缺少同条件论文ωlog"))
    if not finite(value):
        return dict(**base,**unavailable("当前曲线的ωlog无定义，论文参考仍保留"))
    delta=value-paper
    return dict(**{**base,"signed_difference":delta,"absolute_difference":abs(delta),
                   "relative_difference_pct":100*abs(delta)/abs(paper) if paper else None},
                status="available",relative_reason="论文参考为0，相对偏差无定义" if paper==0 else None)


def calculate_alpha(payload,references=None,reference_reasons=None):
    refs=references or {};reasons=reference_reasons or {}
    ref=refs.get("lambda") or {}
    normalization=dict(status="unavailable",method="paper_lambda",label="依据论文 λ 归一化",
                       lambda_reference=ref.get("value") if finite(ref.get("value")) else None,
                       source=ref.get("source"),record_key=ref.get("record_key"),coefficient=None,
                       lambda_normalized=None,reason=reasons.get("lambda") or "缺少同条件论文λ")
    raw=dict(method=METHOD,status="unavailable",pixel_integral=None,pixel_integral_status="unavailable",
             omega_log_k=None,lambda_integral=None,normalization=normalization,parameters={})
    candidate=None
    try:
        curves=[c for c in payload.get("curves",[]) if c["kind"]=="alpha2f"]
        if len(curves)!=1:raise ValueError("当前需要一条明确的α²F目标曲线")
        curve=curves[0]
        relative,basis=pixel_curve(payload,curve)
        f,p=connected_samples(relative,payload.get("manual_documents",{}).get(curve["id"]))
        peak=max(p)
        weighted=spectral_integrals(f,[v/peak for v in p] if peak else p)
        omega_value=weighted["omega_log_k"]
        omega=omega_value if finite(omega_value) else None
        ip=weighted["lambda_integral"]*peak if peak else 0.
        raw.update(status="available",relative_basis=basis,minimum_integrated_thz=f[0],maximum_integrated_thz=f[-1],
                   positive_frequency_complete=True,frequency_log_thz=weighted["frequency_log_thz"] if finite(weighted["frequency_log_thz"]) else None,
                   omega_log_k=omega,
                   pixel_integral=ip if finite(ip) and basis["kind"]!="stored_relative_values" else None)
        raw["pixel_integral_status"]="available" if raw["pixel_integral"] is not None else "unavailable"
        raw["parameters"]["omega_log"]=(dict(status="available",value=omega) if finite(omega)
                                        else unavailable("相对谱加权积分为0，ωlog无定义" if peak==0 else "ωlog超出当前数值范围"))
        normalization["pixel_integral"]=raw["pixel_integral"]
        if raw["pixel_integral"] is None:
            normalization["reason"]="缺少原图像素换算或像素积分溢出，暂不能确定每像素C"
        elif ip<=0:
            normalization["reason"]="像素加权积分为0，无法确定C"
        elif ref and not finite(ref.get("value")):
            normalization["reason"]="论文λ不是有限数值，暂不能确定C"
        elif not finite(ref.get("value")) or not ref.get("source") or not ref.get("same_conditions"):
            normalization["reason"]=reasons.get("lambda") or "缺少同条件论文λ"
        elif ref["value"]<0:
            normalization["reason"]="论文λ为负值，无法生成非负α²F归一化"
        else:
            coefficient=ref["value"]/ip
            normalized=[coefficient*v for v in p]
            if not finite(coefficient) or any(not finite(v) for v in normalized) or (ref["value"]!=0 and coefficient==0):
                normalization["reason"]="归一化倍率超出当前数值范围"
            else:
                integral=spectral_integrals(f,normalized)["lambda_integral"]
                if not finite(integral):raise ValueError("归一化积分数值溢出")
                normalization.update(status="available",coefficient=coefficient,lambda_normalized=integral,reason=None)
                raw["lambda_integral"]=integral
                candidate=dict(status="available",method="paper_lambda",label="依据论文 λ 归一化",curve_id=curve["id"],
                               frequency_thz=f,relative_amplitude=p,alpha2f=normalized,unit="dimensionless",
                               coefficient=coefficient,amplitude_basis=basis,lambda_reference=ref["value"],source=ref["source"])
    except (ValueError,OverflowError,ZeroDivisionError) as exc:
        raw.update(status="unavailable",reason=str(exc))
        raw["parameters"]["omega_log"]=unavailable(exc)
        normalization["reason"]="曲线不能形成有效积分："+str(exc)
    raw["parameters"]["lambda"]=(dict(status="available",value=normalization["lambda_normalized"],method="paper_lambda")
                                 if normalization["status"]=="available" else unavailable(normalization["reason"]))
    return dict(raw=raw,candidate=candidate,
                comparison=omega_comparison(raw["omega_log_k"],refs.get("omega_log"),reasons.get("omega_log")))

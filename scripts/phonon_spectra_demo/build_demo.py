"""从已标定的真实 PDF 生成本地谱线 demo；不连接业务数据库。"""
from __future__ import annotations

import argparse
import base64
import csv
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import io
import json
from pathlib import Path
import sys
from collections import Counter

import numpy as np
from PIL import Image
import pymupdf
from ase.spacegroup import crystal
from ase.data import chemical_symbols
import spglib

from digitize import LinearAxis, extract_curve, normalize_dos, spectral_integrals
from quality import zero_baseline_candidate, cumulative_moments
from scientific_review import verify_review

HERE = Path(__file__).resolve().parent


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def verified_bytes(path: Path, expected: str) -> bytes:
    data = path.read_bytes()
    if sha256(data) != expected:
        raise ValueError(f"来源文件哈希不符：{path.name}")
    return data


def extract_figure(pdf_bytes: bytes, spec: dict) -> bytes:
    with pymupdf.open(stream=pdf_bytes, filetype="pdf") as doc:
        page = doc[spec["pdf_page"] - 1]
        wanted = pymupdf.Rect(spec["bbox_pdf_pt"])
        matches = []
        for item in page.get_images(full=True):
            if list(item[2:4]) != spec["size_px"]:
                continue
            if any(max(abs(a - b) for a, b in zip(rect, wanted)) < .1
                   for rect in page.get_image_rects(item[0])):
                matches.append(doc.extract_image(item[0])["image"])
        if len(matches) != 1:
            raise ValueError("未找到唯一的原始图像；不能复用旧标定")
    data = matches[0]
    if sha256(data) != spec["sha256"]:
        raise ValueError("内嵌图像哈希不符")
    return data


def primitive_structure(spec: dict) -> dict:
    atoms = crystal(spec["symbols"], basis=spec["basis"], spacegroup=spec["spacegroup"],
                    cellpar=spec["cellpar"], symprec=1e-4)
    if len(atoms) != sum(spec["reported_multiplicities"]):
        raise ValueError("展开的原子数与原表多重性不一致")
    primitive = spglib.find_primitive(
        (atoms.cell.array, atoms.get_scaled_positions(), atoms.numbers), symprec=1e-4)
    if primitive is None:
        raise ValueError("原胞化失败")
    return dict(conventional_atoms=len(atoms), primitive_atoms=len(primitive[2]),
                mode_count=3 * len(primitive[2]), atomic_numbers=primitive[2].tolist(),
                symprec_angstrom=1e-4, source=spec)


def csv_text(result: dict) -> str:
    buf = io.StringIO(newline="")
    fields = ["case_id", "material_state", "formula", "phase", "pressure_gpa", "curve",
              "kind", "projection", "frequency_thz", "frequency_pixel", "amplitude_pixel",
              "pixel_low", "pixel_high", "observed_amplitude", "reconstructed_amplitude",
              "conditional_normalized_dos", "unit", "normalized_unit", "normalization_status",
              "normalization_accepted", "primitive_atoms", "normalization_target_modes", "point_status",
              "detection_mode", "zero_baseline_candidate_amplitude", "zero_baseline_candidate_reason", "review_status",
              "training_ready", "scientific_review_status", "quantitative_ml_approved",
              "source_sha256", "pdf_page", "figure"]
    writer = csv.DictWriter(buf, fieldnames=fields)
    writer.writeheader()
    for state in result["material_states"]:
        candidate = state["dos_normalization_candidate"]
        for curve in state["curves"]:
            normalized = candidate.get("components", {}).get(curve["projection"])
            baseline = state.get("precision", {}).get("zero_baseline_candidate", {})
            for i, p in enumerate(curve["points"]):
                has_baseline = curve["kind"] == "alpha2f" and baseline.get("status") == "conditional_candidate"
                writer.writerow(dict(case_id=result["case_id"], material_state=state["id"],
                    formula=state["formula"], phase=state["phase"], pressure_gpa=state["pressure_gpa"],
                    curve=curve["id"], kind=curve["kind"], projection=curve["projection"],
                    frequency_thz=p["frequency_thz"], frequency_pixel=p["frequency_pixel"],
                    amplitude_pixel=p["amplitude_pixel"], pixel_low=p["pixel_low"], pixel_high=p["pixel_high"],
                    observed_amplitude=p["observed_amplitude"], reconstructed_amplitude=p["reconstructed_amplitude"],
                    conditional_normalized_dos=None if normalized is None else normalized[i],
                    unit=curve["unit"], normalized_unit=candidate.get("unit") if normalized is not None else None,
                    normalization_status=candidate.get("status") if curve["kind"] == "phonon_dos" else None,
                    normalization_accepted=False if curve["kind"] == "phonon_dos" else None,
                    primitive_atoms=state.get("structure", {}).get("primitive_atoms"),
                    normalization_target_modes=candidate.get("target_modes") if curve["kind"] == "phonon_dos" else None,
                    point_status=p["status"], detection_mode=p.get("detection_mode"),
                    zero_baseline_candidate_amplitude=baseline["amplitude"][i] if has_baseline else None,
                    zero_baseline_candidate_reason=baseline["point_reasons"][i] if has_baseline else None,
                    review_status=curve["review_status"],
                    training_ready=False,
                    scientific_review_status=result.get("scientific_review", {}).get("status"),
                    quantitative_ml_approved=result.get("scientific_review", {}).get("quantitative_ml_approved"),
                    source_sha256=result["source"]["paper_sha256"],
                    pdf_page=result["source"]["figure"]["pdf_page"], figure=result["source"]["figure"]["label"]))
    return buf.getvalue()


def build(config: dict, pdf: Path, supplement: Path) -> tuple[dict, bytes]:
    paper = verified_bytes(pdf, config["paper_sha256"])
    verified_bytes(supplement, config["supplement_sha256"])
    figure = extract_figure(paper, config["figure"])
    rgb = np.asarray(Image.open(io.BytesIO(figure)).convert("RGB"))
    if [rgb.shape[1], rgb.shape[0]] != config["figure"]["size_px"]:
        raise ValueError("图像尺寸不符")
    result = dict(schema_version=1, case_id=config["case_id"], paper=dict(title=config["title"], doi=config["doi"]),
                  source={k: config[k] for k in ("paper_sha256", "supplement_sha256", "figure", "calibration_method")},
                  provenance=dict(config_sha256=sha256(json.dumps(config, sort_keys=True).encode()),
                                  generated_at=datetime.now(timezone.utc).isoformat(),
                                  python=sys.version.split()[0],
                                  software={n: importlib.metadata.version(n) for n in
                                            ("numpy", "pillow", "pymupdf", "ase", "spglib")},
                                  mode="semi_automatic_digitization", algorithm_version="scientific_audit_v4",
                                  business_database_writes=False),
                  calibration_manifest=config, material_states=[], training_ready=False)
    for state_spec in config["material_states"]:
        frequency_axis = LinearAxis.fit(state_spec["frequency_ticks"], state_spec.get("frequency_scale", "linear"))
        structure = primitive_structure(state_spec["structure"])
        curves = [extract_curve(rgb, c, frequency_axis) for c in state_spec["curves"]]
        dos = [c for c in curves if c["kind"] == "phonon_dos"]
        alpha_curves = [c for c in curves if c["kind"] == "alpha2f"]
        cumulative_curves = [c for c in curves if c["kind"] == "cumulative_lambda"]
        if not dos or len(alpha_curves) != 1 or len(cumulative_curves) != 1:
            raise ValueError("本轮试作每状态需要 DOS 投影、一条 α²F 与一条累计 λ")
        alpha, cumulative = alpha_curves[0], cumulative_curves[0]
        if len({c["projection"] for c in dos}) != len(dos):
            raise ValueError("投影标识重复，不能覆盖或重复计数")
        grid = [p["frequency_thz"] for p in dos[0]["points"]]
        if any(grid != [p["frequency_thz"] for p in c["points"]] for c in dos):
            raise ValueError("投影不在同一频率网格，不能相加")
        norm = normalize_dos(grid,
                {c["projection"]: [p["reconstructed_amplitude"] for p in c["points"]] for c in dos},
                structure["primitive_atoms"], assumptions_confirmed=state_spec["projection_scale_confirmed"])
        norm["assumptions"] = state_spec["projection_assumptions"]
        # 当前数据包含人工标定、图像重建与尚未验收的误差，绝不自动批准。
        norm["accepted"] = False
        f = [p["frequency_thz"] for p in alpha["points"]]
        a = [p["reconstructed_amplitude"] for p in alpha["points"]]
        integrals = spectral_integrals(f, a)
        sensitivity = [spectral_integrals(f, a, cutoff) for cutoff in (.5, 1, 2)]
        observed = [p for p in cumulative["points"] if p["observed_amplitude"] is not None]
        end = observed[-1]
        reference = state_spec["reference"]
        alpha_spec = next(c for c in state_spec["curves"] if c["kind"] == "alpha2f")
        baseline = zero_baseline_candidate(rgb, alpha, alpha_spec)
        if baseline["status"] == "conditional_candidate":
            base_integral = baseline["integral"]
            baseline["raw_minus_candidate_lambda"] = integrals["lambda_integral"] - base_integral["lambda_integral"]
            baseline["lambda_difference_pct"] = 100 * (base_integral["lambda_integral"] / reference["lambda"] - 1)
            baseline["omega_log_difference_pct"] = 100 * (base_integral["omega_log_k"] / reference["omega_log_k"] - 1)
        try:
            moments = cumulative_moments(
                [p["frequency_thz"] for p in cumulative["points"]],
                [p["reconstructed_amplitude"] for p in cumulative["points"]])
            moments["omega_log_difference_pct"] = 100 * (moments["omega_log_k"] / reference["omega_log_k"] - 1)
            moments["endpoint_lambda_difference_pct"] = 100 * (moments["cumulative_endpoint"] / reference["lambda"] - 1)
        except ValueError as exc:
            moments = dict(status="unavailable", reason=str(exc))
        precision = dict(zero_baseline_candidate=baseline, cumulative_moment=moments,
                         automatic_checks=dict(
                             all_curves_continuous=all(c["point_counts"]["missing"] == 0 for c in curves),
                             source_hash_verified=True,
                             zero_reference_valid=baseline["status"] == "conditional_candidate",
                             independent_cumulative_available=moments["status"] == "diagnostic_only"),
                         scientific_acceptance="requires_user_review",
                         unresolved=["DOS 投影共同尺度尚待核实", "零基线候选含分辨率以下幅值按零处理的假设",
                                     "累计谱矩不包含第一个可读正频点以下区间", "原图裁边无法由增加像素恢复"])
        species_counts = Counter(chemical_symbols[z] for z in structure["atomic_numbers"])
        areas = norm.get("component_mode_integrals", {})
        if set(areas) == set(species_counts):
            precision["projection_mode_check"] = dict(
                status="conditional_diagnostic",
                expected={k: 3 * count for k, count in species_counts.items()},
                measured=areas,
                relative_difference_pct={k: 100 * (areas[k] / (3 * count) - 1)
                                         for k, count in species_counts.items()},
                assumption="仅在完整、共同尺度的正交笛卡尔元素投影定义下适用；不把各分波分别强制缩放到目标")
        else:
            precision["projection_mode_check"] = dict(status="unavailable", reason="无法对应完整元素投影")
        diagnostics = dict(**integrals,
                           lambda_reported=reference["lambda"], omega_log_reported_k=reference["omega_log_k"],
                           lambda_difference_pct=100 * (integrals["lambda_integral"] / reference["lambda"] - 1),
                           omega_log_difference_pct=100 * (integrals["omega_log_k"] / reference["omega_log_k"] - 1),
                           cumulative_lambda_endpoint=end["observed_amplitude"],
                           cumulative_endpoint_frequency_thz=end["frequency_thz"],
                           low_frequency_sensitivity=sensitivity,
                           warnings=["图像数字化未获人工验收，不自动用于训练",
                                     "DOS 共尺度与投影归一化定义须按案例核实",
                                     "λ 与 ωlog 为重建曲线诊断；低频像素偏差会被积分放大"])
        if not integrals["positive_frequency_complete"]:
            diagnostics["warnings"].append("α²F 存在缺口：数值仅为连续有效区间的部分积分")
        if alpha["clipped_frequencies_thz"]:
            diagnostics["warnings"].append("α²F 触及图框幅值边界，峰值可能被原图裁切")
        result["material_states"].append(dict(
            **{k: state_spec[k] for k in ("id", "formula", "phase", "pressure_gpa")},
            structure=structure, reference=reference, curves=curves,
            dos_normalization_candidate=norm, diagnostics=diagnostics,
            precision=precision, training_ready=False))
    return result, figure


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--supplement", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--scientific-review", type=Path, help="仅加载与当前数据指纹完全一致的已完成复核记录")
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    out = args.output.resolve()
    for path in (args.pdf, args.supplement, args.config):
        if path.resolve().is_relative_to(out):
            raise ValueError("来源文件不能位于输出目录内")
    result, figure = build(config, args.pdf, args.supplement)
    if args.scientific_review:
        result["scientific_review"] = verify_review(
            json.loads(args.scientific_review.read_text(encoding="utf-8")), result)
    payload = json.dumps(result, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    csv_data = csv_text(result)
    report = dict(schema_version=1, case_id=result["case_id"], training_ready=False,
                  states=[dict(material_state=s["id"], structure=s["structure"],
                               curves=[dict(id=c["id"], point_counts=c["point_counts"],
                                            chromatic_recovered_points=c["chromatic_recovered_points"],
                                            clipped_frequencies_thz=c["clipped_frequencies_thz"]) for c in s["curves"]],
                               normalization={k: v for k, v in s["dos_normalization_candidate"].items()
                                              if k not in ("frequency_thz", "total", "components")},
                               diagnostics=s["diagnostics"],
                               precision=dict(
                                   zero_baseline_candidate={k: v for k, v in s["precision"]["zero_baseline_candidate"].items()
                                                            if k not in ("frequency_thz", "amplitude", "point_reasons")},
                                   cumulative_moment={k: v for k, v in s["precision"]["cumulative_moment"].items()
                                                      if k not in ("monotone_frequency_thz", "monotone_cumulative")},
                                   automatic_checks=s["precision"]["automatic_checks"],
                                   scientific_acceptance=s["precision"]["scientific_acceptance"],
                                   projection_mode_check=s["precision"]["projection_mode_check"],
                                   unresolved=s["precision"]["unresolved"]))
                          for s in result["material_states"]])
    if "scientific_review" in result:
        report["scientific_review"] = result["scientific_review"]
    html = (HERE / "template.html").read_text(encoding="utf-8")
    # JSON 与文献元数据不得闭合脚本标签；图和 CSV 通过 base64 嵌入。
    html = html.replace("__DATA_JSON__", payload.replace("<", "\\u003c"))
    html = html.replace("__FIGURE_BASE64__", base64.b64encode(figure).decode())
    html = html.replace("__CSV_BASE64__", base64.b64encode(csv_data.encode("utf-8")).decode())
    out.mkdir(parents=True, exist_ok=True)
    for name, data in {
        "spectra.json": json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False).encode(),
        "points.csv": csv_data.encode("utf-8"), "figure.png": figure,
        "report.json": json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False).encode(),
        "index.html": html.encode("utf-8"),
    }.items():
        (out / name).write_bytes(data)
    print(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()

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

import numpy as np
from PIL import Image
import pymupdf
from ase.spacegroup import crystal
import spglib

from digitize import LinearAxis, extract_curve, normalize_dos, spectral_integrals

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
              "normalization_accepted", "primitive_atoms", "normalization_target_modes", "point_status", "review_status",
              "training_ready", "source_sha256", "pdf_page", "figure"]
    writer = csv.DictWriter(buf, fieldnames=fields)
    writer.writeheader()
    for state in result["material_states"]:
        candidate = state["dos_normalization_candidate"]
        for curve in state["curves"]:
            normalized = candidate.get("components", {}).get(curve["projection"])
            for i, p in enumerate(curve["points"]):
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
                    point_status=p["status"], review_status=curve["review_status"],
                    training_ready=False, source_sha256=result["source"]["paper_sha256"],
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
                                  mode="semi_automatic_digitization", business_database_writes=False),
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
            dos_normalization_candidate=norm, diagnostics=diagnostics, training_ready=False))
    return result, figure


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--supplement", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    out = args.output.resolve()
    for path in (args.pdf, args.supplement, args.config):
        if path.resolve().is_relative_to(out):
            raise ValueError("来源文件不能位于输出目录内")
    result, figure = build(config, args.pdf, args.supplement)
    payload = json.dumps(result, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    csv_data = csv_text(result)
    report = dict(schema_version=1, case_id=result["case_id"], training_ready=False,
                  states=[dict(material_state=s["id"], structure=s["structure"],
                               curves=[dict(id=c["id"], point_counts=c["point_counts"],
                                            clipped_frequencies_thz=c["clipped_frequencies_thz"]) for c in s["curves"]],
                               normalization={k: v for k, v in s["dos_normalization_candidate"].items()
                                              if k not in ("frequency_thz", "total", "components")},
                               diagnostics=s["diagnostics"]) for s in result["material_states"]])
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

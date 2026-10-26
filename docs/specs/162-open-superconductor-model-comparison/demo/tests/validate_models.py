"""对照作者样本、公开训练表与高精度公式参考；不宣称独立科学精度。"""
import hashlib
from io import StringIO
import json
import math
from pathlib import Path
import sys
import warnings

warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)
DEMO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DEMO))
from inference import CACHE, predict


def main():
    reference = json.loads((CACHE / "bete/reference-cso.json").read_text())
    comparisons = []
    for identifier in ("305", "21", "689"):
        result = predict({"model_id": "bete-cso", "structure": (CACHE / f"bete/structures/{identifier}.cif").read_text(), "format": "cif"})
        lam, wlog = reference["lamb_pred"][identifier], reference["wlog_pred"][identifier]
        tc_reference = wlog / 1.2 * math.exp(-1.04 * (1 + lam) / (lam - .09 * (1 + .62 * lam)))
        error = abs(result["tc"] - tc_reference)
        spectrum_error = max(abs(a - b) for a, b in zip(result["spectrum"]["a2f"], reference["pred_avg"][identifier]))
        # 本地工程回归边界。当前 806 条结构与作者 824 条参考输出版本不同，记录实际差异，不称逐位复现。
        assert error < .02 and spectrum_error < .001, (identifier, error, spectrum_error)
        assert result["ensemble_size"] == 100
        comparisons.append({"id": identifier, "formula": result["formula"], "tc": result["tc"], "published_reference_tc": tc_reference, "tc_difference_K": error, "max_spectrum_difference": spectrum_error})
    from ase.io import read, write
    atoms = read(CACHE / "bete/structures/305.cif")
    atoms.set_cell(atoms.cell * 1.01, scale_atoms=True)
    text = StringIO(); write(text, atoms, format="vasp")
    novel = predict({"model_id": "bete-cso", "structure": text.getvalue(), "format": "vasp"})
    assert math.isfinite(novel["tc"]) and abs(novel["tc"] - comparisons[0]["tc"]) > .001
    lines = (CACHE / "datasets/sisso-2019-train.dat").read_text().splitlines()[1:]
    errors = []
    for line in lines:
        name, target, omega, lam, mu = line.split()
        result = predict({"model_id": "sisso-2019", "parameters": {"lambda": lam, "omega_log": omega, "mu_star": mu}})
        errors.append((result["tc"] - float(target)) ** 2)
    rmse = math.sqrt(sum(errors) / len(errors))
    assert len(errors) == 29 and .245 < rmse < .26  # 对照论文训练 RMSE 约 0.25 K。
    high = predict({"model_id": "sisso-2022", "parameters": {"lambda": 2, "omega_log": 1000, "omega_2": 1500, "mu_star": .1}})
    # 论文式 (6)–(8) 用独立 mpmath 60 位算术所得参考，不冒充原始材料标签。
    assert abs(high["tc"] - 209.3154165353737031339950241820391) < 1e-10
    bad = [
        {"model_id": "bete-cso", "structure": "not a crystal", "format": "cif"},
        {"model_id": "sisso-2019", "parameters": {"lambda": "nan", "omega_log": 100, "mu_star": .1}},
        {"model_id": "sisso-2022", "parameters": {"lambda": 2, "omega_log": 1000, "omega_2": 900, "mu_star": .1}},
        {"model_id": "sisso-2022", "parameters": {"lambda": 1, "omega_log": 900, "omega_2": 1000, "mu_star": .1}},
    ]
    for request in bad:
        try:
            predict(request)
        except ValueError:
            pass
        else:
            raise AssertionError("非法输入未被拒绝")
    report = {"status": "passed", "bete": comparisons, "synthetic_strained_Nb_tc": novel["tc"], "sisso2019_training_rmse": rmse, "sisso2022_formula_check": high["tc"], "invalid_cases": len(bad), "reference_sha256": hashlib.sha256((CACHE / "bete/reference-cso.json").read_bytes()).hexdigest(), "limits": ["BETE 是当前发布版本的近似数值回归，不是逐位复现或独立性能评测", "Xie 2022 原始训练包下载失败，只验证公开公式与输入边界", "合成形变结构仅验证新输入真实经过模型，不代表该结构物理稳定或 Tc 正确"]}
    (DEMO.parent / "assets").mkdir(exist_ok=True)
    (DEMO.parent / "assets/demo-model-validation.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

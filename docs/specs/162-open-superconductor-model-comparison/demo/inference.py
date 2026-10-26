"""运行作者权重／公开解析模型，不读取参考预测表返回结果。"""
from functools import lru_cache
from io import StringIO
import json
import math
from pathlib import Path
import sys
from types import SimpleNamespace
import threading
import time

ROOT = Path(__file__).resolve().parents[4]
CACHE = ROOT / ".local/tc-model-demo"
REVISION = "56bc783908a60e8a15e31b60018e6f3c3e48f593"
_LOCK = threading.Lock()


def parse_structure(text, fmt="auto"):
    """按内容识别结构；显式指定格式时保留选择并提示不匹配。"""
    from ase.io import read
    if fmt not in ("auto", "cif", "vasp"):
        raise ValueError("请选择自动识别、CIF 或 POSCAR／CONTCAR")
    if not text.strip() or len(text.encode()) > 256 * 1024:
        raise ValueError("请提供非空且不超过 256 KiB 的结构文件")
    text = text.lstrip("\ufeff")
    names = {"cif": "CIF", "vasp": "POSCAR／CONTCAR"}
    candidates = ("cif", "vasp") if fmt == "auto" else (fmt,)
    for candidate in candidates:
        try:
            atoms = read(StringIO(text), format=candidate)
            if len(atoms):
                return atoms, candidate
        except Exception:
            continue
    if fmt != "auto":
        other = "vasp" if fmt == "cif" else "cif"
        try:
            alternate = read(StringIO(text), format=other)
        except Exception:
            alternate = None
        if alternate is not None and len(alternate):
            raise ValueError(f"当前选择了 {names[fmt]}，但内容可按 {names[other]} 读取；请选择“自动识别”或 {names[other]}")
    raise ValueError("无法读取结构，请提供完整的 CIF 或 POSCAR／CONTCAR 内容（包括晶胞、元素和全部原子坐标）")


def parameters(values, require_w2=False):
    required = ["lambda", "omega_log", "mu_star"] + (["omega_2"] if require_w2 else [])
    parsed = {}
    for key in required:
        try:
            value = float(values[key])
        except (KeyError, ValueError, TypeError):
            raise ValueError(f"参数 {key} 必须为数值") from None
        if not math.isfinite(value) or value <= 0:
            raise ValueError(f"参数 {key} 必须为有限正数")
        parsed[key] = value
    if not 0.01 <= parsed["lambda"] <= 10:
        raise ValueError("Demo 的 λ 输入范围为 0.01–10；这不是模型精度保证范围")
    if not 0.01 <= parsed["mu_star"] <= 0.5:
        raise ValueError("μ* 输入范围为 0.01–0.5")
    if parsed["omega_log"] > 10000 or parsed.get("omega_2", 0) > 10000:
        raise ValueError("频率参数请以 K 输入，Demo 上限为 10000 K")
    if require_w2 and parsed["omega_2"] < parsed["omega_log"]:
        raise ValueError("同一非负谱的 ω₂ 不应小于 ωlog，请核对定义与单位")
    return parsed


def sisso(model_id, values):
    p = parameters(values, model_id == "sisso-2022")
    lam, wlog, mu = p["lambda"], p["omega_log"], p["mu_star"]
    if model_id == "sisso-2019":
        # Xie 2019 论文式 (4)，保留论文系数，不替换为其他拟合版本。
        tc = 0.09525 * lam**4 * wlog / (lam**3 + math.sqrt(mu))
        method = "Xie 2019，式 (4)"
        warning = "训练于 29 个低 Tc 材料；高压输入属于外推，不代表高压专用模型。"
    elif model_id == "sisso-2022":
        ratio = wlog / p["omega_2"]
        denominator = lam - mu * (1 + 0.62 * lam)
        correction_denominator = 1 / lam - mu - ratio
        if denominator <= 0 or abs(correction_denominator) < 1e-6:
            raise ValueError("参数落在公式不适用区或修正项奇点附近，不能给出有效 Tc")
        f_omega = 1.92 * (lam + ratio - mu**(1 / 3)) / (math.sqrt(lam) * math.exp(ratio)) - 0.08
        f_mu = 6.86 * math.exp(-lam / mu) / correction_denominator + 1
        if f_omega <= 0 or f_mu <= 0:
            raise ValueError("学习修正因子非正，当前参数不能给出有效 Tc")
        tc = f_omega * f_mu * wlog / 1.2 * math.exp(-1.04 * (1 + lam) / denominator)
        method = "Xie 2022，式 (6)–(8)"
        warning = "需要已有 EPC 参数；论文氢化物外推验证不保证任意压力或非谐体系精度。"
    else:
        raise ValueError("未知参数模型")
    if not math.isfinite(tc) or tc < 0:
        raise ValueError("模型没有产生有效 Tc")
    return {"model_id": model_id, "tc": tc, "parameters": p, "method": method, "warning": warning, "units": {"tc": "K", "omega_log": "K", "omega_2": "K"}}


class BetePredictor:
    def __init__(self):
        import numpy as np
        import torch
        # e3nn 0.4.2 自带常量含 Python slice，显式允许这一内置类型；权重仍使用 weights_only。
        with torch.serialization.safe_globals([slice]):
            from e3nn import o3  # noqa: F401
        sys.path.insert(0, str(CACHE / "bete"))
        from utils.model import PeriodicNetwork
        from utils.data import build_data
        from ase.io import read
        from ase.neighborlist import neighbor_list
        from torch_geometric.data import Batch

        self.torch, self.np, self.build_data, self.Batch = torch, np, build_data, Batch
        torch.set_num_threads(2)
        torch.set_default_dtype(torch.float64)
        total_edges = total_atoms = 0
        for path in sorted((CACHE / "bete/structures").glob("*.cif")):
            atoms = read(path)
            total_edges += len(neighbor_list("i", atoms, 4.0, self_interaction=True))
            total_atoms += len(atoms)
        if not total_atoms:
            raise ValueError("原始结构未准备完成")
        self.num_neighbors = total_edges / total_atoms
        self.model = PeriodicNetwork(in_dim=118, em_dim=64, irreps_in="64x0e", irreps_out="51x0e", irreps_node_attr="64x0e", layers=2, mul=32, lmax=1, max_radius=4, num_neighbors=self.num_neighbors, reduce_output=True, p=0.0)
        self.model.eval()

    def predict(self, text, fmt):
        from ase.neighborlist import neighbor_list
        atoms, actual_format = parse_structure(text, fmt)
        if not 1 <= len(atoms) <= 80 or not self.np.isfinite(atoms.positions).all() or not self.np.isfinite(atoms.cell.array).all():
            raise ValueError("结构必须包含 1–80 个原子，坐标与晶胞必须为有限数")
        if atoms.get_volume() / len(atoms) < 2 or not atoms.pbc.all():
            raise ValueError("晶胞必须三维周期且每原子体积不小于 2 Å³；请核对结构单位")
        if atoms.info.get("occupancy"):
            if any(len(v) != 1 or any(abs(float(o) - 1) > 1e-6 for o in v.values()) for v in atoms.info["occupancy"].values()):
                raise ValueError("当前模型 Demo 不支持分数占位结构")
        if len(neighbor_list("i", atoms, 4, self_interaction=True)) > 20000:
            raise ValueError("近邻图过大，请使用较小原胞")
        entry = SimpleNamespace(structure=atoms, target=self.np.zeros(51))
        graph = self.build_data(entry, embed_ph_dos=False, embed_e_dos=False, r_max=4)
        graph = self.Batch.from_data_list([graph])
        spectra = []
        with self.torch.inference_mode():
            for i in range(100):
                path = CACHE / "bete/CSO" / f"model_cso_{i}.pt"
                state = self.torch.load(path, map_location="cpu", weights_only=True)
                self.model.load_state_dict(state, strict=True)
                # 作者 forward 会改写 x／z，每个网络必须使用原始图的独立副本。
                spectra.append(self.model(graph.clone()).cpu().numpy()[0])
        spectrum = self.np.mean(spectra, axis=0)
        frequency = self.np.arange(0.25, 101, 2)
        if not self.np.isfinite(spectrum).all() or (spectrum < 0).any():
            raise ValueError("模型产生无效谱")
        # 与作者 Pred_CSO notebook 一致的右端点求和，不擅自换积分方法。
        lam = float(2 * self.np.sum(spectrum[1:] / frequency[1:] * 2))
        if lam <= 0:
            raise ValueError("预测谱无法得到正的 λ")
        wlog = float(self.np.exp(2 * self.np.sum(spectrum[1:] * self.np.log(frequency[1:]) / frequency[1:] * 2) / lam) / 0.08617)
        w2 = float(self.np.sqrt(2 * self.np.sum(spectrum[1:] * frequency[1:] * 2) / lam) / 0.08617)
        mu = 0.09
        denominator = lam - mu * (1 + 0.62 * lam)
        # 分母非正时不把公式发散解释成超高 Tc；谱和参数仍可用于核查。
        tc = wlog / 1.2 * math.exp(-1.04 * (1 + lam) / denominator) if denominator > 0 else None
        return {"model_id": "bete-cso", "tc": tc, "formula": atoms.get_chemical_formula(), "input_format": actual_format, "parameters": {"lambda": lam, "omega_log": wlog, "omega_2": w2, "mu_star": mu}, "spectrum": {"frequency": frequency.tolist(), "a2f": spectrum.tolist(), "unit": "meV"}, "ensemble_size": 100, "method": "BETE-NET-CSO，100 网络平均谱＋作者 Tc 后处理", "version": REVISION, "warning": "0.25–100.25 meV 谱网格；高压氢化物及非谐效应未获本 Demo 验证。" if tc is not None else "已得到谱；Tc 公式分母非正，当前参数无法给出有效 Tc。", "units": {"tc": "K", "omega_log": "K", "omega_2": "K"}}


@lru_cache(maxsize=1)
def predictor():
    return BetePredictor()


def predict(request):
    start = time.monotonic()
    model = request.get("model_id")
    if model == "bete-cso":
        if not _LOCK.acquire(blocking=False):
            raise RuntimeError("结构模型正在运行，请稍后重试")
        try:
            result = predictor().predict(request.get("structure", ""), request.get("format", "auto"))
        finally:
            _LOCK.release()
    else:
        result = sisso(model, request.get("parameters", {}))
    result["elapsed_seconds"] = round(time.monotonic() - start, 3)
    return result

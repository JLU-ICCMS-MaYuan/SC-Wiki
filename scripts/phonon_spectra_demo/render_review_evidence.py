"""从原始位图生成复核位置图；标注为派生证据，原图不改。"""
from pathlib import Path
import argparse
import json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
from PIL import Image


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--figure", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--svg", type=Path, required=True)
    parser.add_argument("--png", type=Path, required=True)
    parser.add_argument("--font", type=Path, required=True)
    args = parser.parse_args()
    font = FontProperties(fname=str(args.font))
    plt.rcParams.update({"font.size": 11, "svg.fonttype": "path"})
    image = Image.open(args.figure)
    fig, axes = plt.subplots(2, 2, figsize=(12, 9), layout="constrained")
    def text(ax, x, y, label, **kwargs):
        ax.text(x, y, label, fontproperties=font, **kwargs)
    def crop(ax, box, title):
        ax.imshow(image.crop(box), extent=[box[0], box[2], box[3], box[1]], interpolation="nearest")
        ax.set_title(title, fontproperties=font, loc="left", fontsize=12, pad=13)
        ax.set_xlabel("原图 x / 像素", fontproperties=font)
        ax.set_ylabel("原图 y / 像素", fontproperties=font)
    ax = axes[0, 0]
    crop(ax, (781, 932, 838, 960), "A  25 THz 位于粉色累计 λ 的虚线空隙")
    ax.axhline(949.17, color="#126681", lw=1, ls=":")
    ax.plot([812, 814], [951, 942], "o", color="#a73c72", ms=4, fillstyle="none")
    text(ax, 829, 949, "25 THz", color="#126681", fontsize=9, ha="right", va="bottom")
    ax = axes[0, 1]
    crop(ax, (938, 898, 984, 919), "B  约 28.6–29.0 THz 的绿峰抵达右图框")
    ax.axvline(977, color="#b16a21", lw=1, ls=":")
    text(ax, 976, 899, "x=977 黑框", color="#8a4c0c", fontsize=9, ha="right", va="top")
    ax = axes[1, 0]
    crop(ax, (778, 639, 794, 660), "C  黑轴 x=781；带色像素 x=782–783")
    ax.set_xticks([781, 782, 783, 790])
    text(ax, 784.5, 643, "贴轴线宽不能区分\n严格零与很小正值", fontsize=10, va="top")
    ax = axes[1, 1]
    audit = json.loads(args.audit.read_text())
    state = next(s for s in audit["states"] if s["id"] == "im3m-200gpa")
    b = next(b for b in state["bins"] if b["frequency_thz"] == [20., 25.])
    lower, upper = [b["cumulative_observed_envelope"][k] for k in ("lower", "upper")]
    ax.set_title("D  Im-3m：20–25 THz 的耦合贡献 Δλ", fontproperties=font, loc="left", fontsize=12, pad=13)
    ax.plot([lower, upper], [3, 3], lw=9, color="#d8e7ec", solid_capstyle="butt")
    text(ax, (lower + upper) / 2, 3.23, f"原图支持范围 {lower:.3f}–{upper:.3f}", ha="center", fontsize=10)
    for y, key, label, color in [(2, "lambda_from_cumulative", "旧直线插值点估计", "#a73c72"),
                                  (1, "lambda_from_alpha", "原 α²F 候选积分", "#28843b"),
                                  (0, "joint_candidate_lambda", "联合重建候选", "#126681")]:
        ax.plot(b[key], y, "o", color=color)
        text(ax, b[key] + .008, y, f"{label} {b[key]:.3f}", va="center", fontsize=10)
    ax.set_xlim(.16, .46)
    ax.set_ylim(-.6, 3.6)
    ax.set_yticks([])
    ax.set_xlabel("Δλ（无量纲）", fontproperties=font)
    ax.spines[["top", "right", "left"]].set_visible(False)
    fig.suptitle("原 PDF 位图局部证据 · 最近邻放大，坐标沿用原图", fontproperties=font, fontsize=16)
    args.svg.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.svg)
    args.svg.write_text("\n".join(line.rstrip() for line in args.svg.read_text().splitlines()) + "\n")
    fig.savefig(args.png, dpi=160)
    plt.close(fig)


if __name__ == "__main__":
    main()

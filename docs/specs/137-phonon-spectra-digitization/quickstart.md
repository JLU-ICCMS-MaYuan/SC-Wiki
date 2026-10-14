# 快速验证

从仓库根目录使用已安装依赖的 Python：

```bash
python "scripts/phonon_spectra_demo/build_demo.py" --config "scripts/phonon_spectra_demo/cases/h3s-2014.json" --pdf ".data/upload_PDFs/947214683efc415abd9b1d64c457d86c/103e9de9802e41e397429b8b801c89d8.pdf" --supplement ".data/upload_PDFs/947214683efc415abd9b1d64c457d86c/8c30c34dc56d45afa6e153aa999eb0d1.pdf" --output "demo/phonon-spectra"
python -m unittest discover -s "scripts/phonon_spectra_demo/tests" -v
```

当前机器 Python 位于 /Users/mayuan/software/miniconda3/envs/sc-wiki/bin/python；其他机器只需满足 scripts 目录 requirements.txt，不要求该绝对路径。源文件迁移后通过参数指定并校验同一哈希。

直接打开 demo/phonon-spectra/index.html；或在该目录使用 localhost 静态文件服务。核对两物相、各四条曲线及总 DOS 条件预览；切换原图叠加与频谱，检查采样点状态并下载 JSON/CSV。DOS 共尺度未确认和 training_ready=false 应始终可见。正式数据库无变更。

精度核验版本可选择“α²F（零基线候选）”，查看原始积分→候选积分、零参考像素区间、独立累计谱 ωlog 与单调调整量。逐点表及 CSV 将原始、重建、零基线候选分列；JSON 另存累计谱单调候选和元素模式数条件对照。不要把“来源与可计算性 4/4”误解为用户科学采纳。

重建带本次科学复核的页面时，在 build_demo.py 命令中增加：

```text
--scientific-review "docs/specs/137-phonon-spectra-digitization/h3s-2014-scientific-review-v5.json"
```

只有数据指纹完全相同才会加载；修改标定、算法或数值后拒绝旧复核。独立计算证据可用：

```bash
python "scripts/phonon_spectra_demo/scientific_review.py" --input "demo/phonon-spectra/spectra.json" --output "/tmp/scwiki137-scientific-metrics.json"
```

该命令只计算证据，不自行授予科学采纳。完整结论见 scientific-review.md；依赖 SciPy 已固定在独立 requirements.txt，无需修改生产环境。

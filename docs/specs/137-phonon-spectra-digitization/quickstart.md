# 快速验证

从仓库根目录使用已安装依赖的 Python：

```bash
python "scripts/phonon_spectra_demo/build_demo.py" --config "scripts/phonon_spectra_demo/cases/h3s-2014.json" --pdf ".data/upload_PDFs/947214683efc415abd9b1d64c457d86c/103e9de9802e41e397429b8b801c89d8.pdf" --supplement ".data/upload_PDFs/947214683efc415abd9b1d64c457d86c/8c30c34dc56d45afa6e153aa999eb0d1.pdf" --output "demo/phonon-spectra"
python -m unittest discover -s "scripts/phonon_spectra_demo/tests" -v
```

当前机器 Python 位于 /Users/mayuan/software/miniconda3/envs/sc-wiki/bin/python；其他机器只需满足 scripts 目录 requirements.txt，不要求该绝对路径。源文件迁移后通过参数指定并校验同一哈希。

直接打开 demo/phonon-spectra/index.html；或在该目录使用 localhost 静态文件服务。核对两物相、各四条曲线及总 DOS 条件预览；切换原图叠加与频谱，检查采样点状态并下载 JSON/CSV。DOS 共尺度未确认和 training_ready=false 应始终可见。正式数据库无变更。

# 本地 Demo 使用与启动

当前入口：[模型实验室](http://127.0.0.1:5189/)。独立推理 API 为 `127.0.0.1:8192`；原网站仍在 `127.0.0.1:5173`。这是用户授权的本机原生实时开发环境，没有部署到阿里云或 Docker。

## 直接体验

1. 常压组选择 BETE-NET-CSO，点击“Nb 铌”载入作者公开结构，或上传自己的 CIF／POSCAR／CONTCAR，然后“运行模型”。
2. 查看实际 100 网络平均谱、Tc、λ、ωlog、ω₂。点击“用此参数对比 SISSO”，运行参数模型；两次结果独立保留。
3. 模型右侧下载数据；点击“论文链接”或“原始网站”查询来源，不再显示长网址和许可／版本。代码与数据在同一仓库时只有一个网站入口。
4. 高压组可运行 Xie 2022 公开公式；“加载示例”只是计算参数示例，不对应某个特定氢化物。其原始训练 ZIP 所在服务当前返回 503，页面明确显示“暂不可下载”。
5. 高压组选择 **Tc assessment model**（姜博文等人的论文称呼），在本页上传 CONTCAR／POSCAR 和包含 PDOS_H.dat 的多份电子 PDOS，再运行并查看 Tc 及全部中间量。请求直接复用原 API，不跳转到其他页面；此功能需要本机原站 8080／8000 服务运行。

BETE-NET 现在只下载一个约 28 MB 的数据包，包含当前公开的 806 条性质记录、对应结构和训练／测试名单，以及许可证和来源说明；作者原文件未改写。SISSO 2019 默认下载实际训练用的 29 条数据。81 样本数据可下载，该候选未接入推理。

## 重建此 Demo

在仓库根执行。需已有主项目原生运行环境、前端依赖与可使用的 GitHub CLI；读取公开 Git 对象仍可能受网络影响。BETE 权重约 1.97 GB，另有约 89 MB 数据和约 93 MB 作者参考输出，准备前预留数 GB 空间。

```bash
scwiki_python_prefix="$(python3 -m scripts.local_deploy.environment "$PWD")"
"$scwiki_python_prefix/bin/python" -m venv --system-site-packages ".local/tc-model-demo/venv"
".local/tc-model-demo/venv/bin/python" -m pip install --no-deps --no-build-isolation -r "docs/specs/162-open-superconductor-model-comparison/demo/requirements-demo.txt"
python3 "docs/specs/162-open-superconductor-model-comparison/demo/scripts/prepare.py"
python3 "docs/specs/162-open-superconductor-model-comparison/demo/scripts/start.py"
```

独立 venv 只读继承主环境的 NumPy／PyTorch／FastAPI 等；额外包安装在 Demo venv，不升级主环境。当前验证使用 Apple Silicon、Python 3.12、PyTorch 2.14、NumPy 1.26.4，以及固定的 e3nn 0.4.2、ASE 3.22.0、PyG 2.0.2。其他机器／Torch 版本需要重新编译扩展并数值核验，不能直接宣称兼容。

`prepare.py` 固定作者提交和 Git blob，逐文件校验后写入专用缓存；重跑复用已经校验的文件。原训练 ZIP 恢复可访问时，会按发布方大小与 MD5 检查后保存，不生成替代数据。服务通过固定白名单供应数据。

`start.py` 只启动本 Demo 的两项进程。端口占用时拒绝抢占；当前已经运行时不需要再启动。前端使用 Vite，API 使用 `uvicorn --reload`；日志和进程身份位于 `.local/tc-model-demo/api.log`、`web.log`、`processes.json`。不要用 `make stop` 停止其他正在运行的项目服务。

模型、原文件和独立 venv 都在被 Git 忽略的 `.local/tc-model-demo/`，不会随代码提交；迁移 Demo 时重跑准备流程或按哈希转移这个目录。

## 验证命令

```bash
npm --prefix "docs/specs/162-open-superconductor-model-comparison/demo" run build
".local/tc-model-demo/venv/bin/python" "docs/specs/162-open-superconductor-model-comparison/demo/tests/validate_models.py"
npm --prefix "docs/specs/162-open-superconductor-model-comparison/demo" run test:browser
```

浏览器验收依赖本机 Playwright 和 Chrome，读取真实服务，实际下载原文件并计算 SHA-256，不模拟预测 API。数值回归与工程验证的具体结果及边界见 [Demo 验证](demo-validation.md)。

# 四工具正式流程与历史 demo 验证入口

## 当前正式入口

在 sc-wiki 环境执行 `python scripts/setup_pdf_tools.py` 准备隔离 Marker/llama.cpp，保持既有 GROBID 服务可用，按 [本地开发指南](../../local-dev.md) 重启 Python/Worker。登录后上传正文和补充材料即可；新任务只有 complementary，DeepSeek thinking 关闭，不手动选择解析器。

真实解析与科学校验可执行：

```bash
python -m scripts.complementary_pdf_demo.production_run --case scripts/complementary_pdf_demo/cases/h3s-2014.json --output demo/complementary-pdf/four-tool-production --extract
python -m pytest backend/tests/test_complementary_pdf.py -q
```

`--resume-dir` 复用经文件哈希验证的 IR；`--reuse-extraction` 只复用完全相同输入的真实原始模型响应，重新执行当前规范化/来源校验，并保存 reuse.json。复用不算新推理，失败记录不覆盖。输出科学 JSON 与 Claim 检查，不代替全部结构/字段的正式上传测试。

完整工作流用 `scripts/check_pdf_workflow.py --pdf <正文.pdf> --output <新目录>`：仅本机新建 test_issue136_* 隔离库，复制已迁移 DDL 和公开分类/表单，启动私有 Redis，经 HTTP/JWT、真实 RQ、四工具、真实模型、草稿保存、证据检查和待审提交验证。不会向业务库写入论文；测试库/制品保留复查，不自动删除。`--resume` 在同一输出目录通过正式重试 API 继续，重试历史另存。凭据由私有 .env 读取，不保存到验证输出。
案例需要人工补理论二级类型时，可显式使用 `--review-theoretical-subtype calculation`；测试会保存原摘要、理由和人工操作证据，不能把该步骤算为模型自动填写。该参数不更改科学值，其他 PDF 应按其实际贡献决定类型。

## 历史三引擎比较入口

前提：项目 Python 可导入 Docling、MinerU、当前表单契约，现有默认 LLM 配置可用；Marker 使用隔离 Python 环境及实际所需模型。所有生成产物在本机 demo 目录，不会自动发布论文。

本轮可直接查看：`demo/complementary-pdf/runs/20261013T072756Z-c15a7ebd/index.html`。先看“效果核对”，再看“字段对照”和各路表单。结果、安装版本与未通过项见 [验证记录](validation.md)。

Marker 隔离安装：

```bash
uv venv --python "/Users/mayuan/software/miniconda3/envs/sc-wiki/bin/python" ".local/issue136-marker"
uv pip install --python ".local/issue136-marker/bin/python" \
  -r "scripts/complementary_pdf_demo/requirements-marker-lock.txt"
```

还需把官方 llama.cpp macOS arm64 包解压到 `.local/issue136-llama/`；脚本仅在子进程 PATH 中发现其中 `llama-server`，不要求全局安装。实际版本及校验摘要见验证记录。当前公开模型下载端点为 hf-mirror.com，禁用隐式令牌；模型下载完成后实际解析在本地执行。

```bash
"/Users/mayuan/software/miniconda3/envs/sc-wiki/bin/python" -m scripts.complementary_pdf_demo.run \
  --case "scripts/complementary_pdf_demo/cases/h3s-2014.json" \
  --output "demo/complementary-pdf" \
  --marker-python ".local/issue136-marker/bin/python" --stage parse
```

解析完成后使用输出的实际运行目录继续（将下方 `<run-id>` 替换为该次输出）：

```bash
"/Users/mayuan/software/miniconda3/envs/sc-wiki/bin/python" -m scripts.complementary_pdf_demo.run \
  --run-dir "demo/complementary-pdf/runs/<run-id>" --stage extract
"/Users/mayuan/software/miniconda3/envs/sc-wiki/bin/python" -m scripts.complementary_pdf_demo.run \
  --run-dir "demo/complementary-pdf/runs/<run-id>" --stage report
```

如果解析中断或某引擎尚未准备好，可保留成功产物并明确恢复：

```bash
"/Users/mayuan/software/miniconda3/envs/sc-wiki/bin/python" -m scripts.complementary_pdf_demo.run \
  --run-dir "demo/complementary-pdf/runs/<run-id>" --stage parse --resume-parsing
```

恢复会验证输入与成功产物摘要，旧失败目录移入 `failed-attempts` 后重跑；成功的原始结果不会被改写。修改解析算法或配置需要新建运行，不能把旧 IR 当成新代码的实测。

在四路生成完成后，独立评测并刷新报告：

```bash
"/Users/mayuan/software/miniconda3/envs/sc-wiki/bin/python" -m scripts.complementary_pdf_demo.evaluate \
  --run-dir "demo/complementary-pdf/runs/<run-id>" \
  --reference "scripts/complementary_pdf_demo/cases/h3s-2014-audit.json"
"/Users/mayuan/software/miniconda3/envs/sc-wiki/bin/python" -m scripts.complementary_pdf_demo.run \
  --run-dir "demo/complementary-pdf/runs/<run-id>" --stage report
```

参考清单检查输入摘要，不得用于其他 PDF，更不得传给生成模型。更换论文时替换输入清单；`cases/calcium-hydride-smoke.json` 是本机已执行的第二输入示例，没有科学准确度验收。

直接打开该目录 `index.html`：检查四路状态、论文/材料/结构/物性表单、证据和覆盖；修改一项核对状态并导出，再刷新导入，确认相同运行的判断可恢复。错误来源/运行 ID 的导入必须拒绝。真实结果与具体环境安装命令补记在 `validation.md`。

```bash
"/Users/mayuan/software/miniconda3/envs/sc-wiki/bin/python" -m pytest \
  "scripts/complementary_pdf_demo/tests/test_demo.py" -q
```

自动检查：输入哈希错误、文件/页不混合、几何差异保留、表格跨度、缺坐标、一对多匹配、失败与重跑保留、HTML 转义、核对分母。真实解析与模型调用不能被这些局部测试替代。额外替换一份本地 PDF 清单运行入口，验证没有 H3S 常量依赖。

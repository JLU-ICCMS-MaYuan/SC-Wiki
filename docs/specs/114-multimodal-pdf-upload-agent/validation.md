# #114 阶段验证记录

## 2026-09-24：Docling 与 MinerU 适配

本轮范围为 T010/T011 及必要的 IR、上传文本兼容桥修复。不是 #114 整体验收。

### 安装

项目 Conda 环境 `/home/mayuan/soft/miniconda3/envs/sc-wiki`：Python 3.12.14；
Docling 2.130.0、MinerU 4.0.6、docling-core 2.98.0、DocVortex 0.4.25、
torch 2.10.0+cpu、torchvision 0.25.0+cpu、NumPy 1.26.4、OpenCV 4.11.0.86。
安装没有替换 NumPy 主版本，`python -m pip check` 报告无损坏依赖。
先使用 `/tmp/scwiki-issue114-parsers` 隔离安装验证，再在项目环境按基础依赖约束安装。

首次直连 Hugging Face 失败；通过镜像并关闭 Xet 下载相同 Docling 权重后成功。
镜像设置仅用于当前测试进程，没有写入系统或项目配置。模型缓存留在本机供再次运行。

### 验证命令和结果

在项目 Python 环境执行；`DEBUG` 的宿主机值不是合法布尔值，测试进程移除此变量：

```bash
env -u DEBUG HF_ENDPOINT=https://hf-mirror.com HF_HUB_DISABLE_XET=1 \
  ISSUE114_REAL_PARSERS=1 DATABASE_URL=sqlite:////tmp/issue114-tests.db \
  JWT_SECRET_KEY=test-only-secret python -m pytest -q \
  "tests/01_decentralized_uploading/test_issue114_structured_parsers.py" \
  "tests/01_decentralized_uploading/test_issue114_multimodal_pdf_agent.py" \
  "backend/tests/test_upload_jobs.py" "backend/tests/test_upload_contracts.py"
```

结果：**80 项通过**。已有 spglib/passlib 弃用警告，未作为失败处理。

- Docling CPU 实际读取两页 PDF（含空白页），输出可定位文本及真实解析器版本。
- MinerU flash/txt 实际读取数字 PDF；测试明确声明该档位，不作为 OCR 成功依据。
- MinerU basic/ocr 实际读取纯图像 PDF，断言原 PDF 没有文本层，输出含
  `200 K` 与 `150 GPa` 的 OCR 文本和 bbox。
- Docling 原生 `DoclingDocument` 类型覆盖表格单元、图像、公式与坐标原点转换。
- MinerU Middle JSON 映射覆盖归一化 bbox、HTML rowspan、行列和缺失单元格坐标。
- 真实子进程超时终止、非法媒体拒绝、无依赖不切换、NaN/越界/不存在页面拒绝。
- 实际 PyMuPDF → 上传 IR 文件保存；分段缓存按方案和文本摘要隔离；上传契约回归。

### 未完成验收

尚无 50 篇人工标注基准；复杂真实论文召回率、曲线和跨页表格语义未验证。
MinerU standard/advanced 和原生 PDF LLM 供应商未验证。没有运行 MySQL 迁移、完整
Redis/RQ 上传验收、前端或 Docker 镜像验收；默认配置保持 legacy，没有自动发布科学数据。

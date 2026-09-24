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


## 2026-09-24：证据门禁、持久化与前端接入

本轮新增以下验证：

- 全部 `test_issue114_*.py` 加上传作业/上传契约测试：**106 项通过、1 项跳过**。
  跳过项需要专门 MySQL 地址，已另用新建的独立 MySQL 8.4.2 实例运行通过；测试
  实例禁用网络监听，仅使用临时 Unix socket，结束后关闭并清理临时目录。
- 独立 MySQL 测试批次 **29 项通过**，覆盖真正执行 #114 增量 DDL、当前 revision
  级联更新、事务回滚、依赖删除与降级，不用 SQLite 结果替代 MySQL 证据。
- SQLite 实际事务保存 IR、运行、块和定位关联；跨文件拒绝、幂等关联、区域页面 PNG
  渲染、源文件哈希变化拒绝和旧文本兼容通过。新上传任务用真实 PyMuPDF/IR/Claim/
  覆盖检查到 ready 或 failed；模型响应固定注入，不代表模型科学正确率。
- EvidenceRegion、共享 EvidenceWorkflow、上传任务工作区：**45 项前端测试通过**。
  请求仅在点击时触发，源变化不会显示迟到的旧区域；错误保留原文；解析方案控件保留
  多文件清单和原上传行为。前端 TypeScript/生产构建通过；既有分包体积提示保留。
- `go test ./models` 通过；新增映射显式使用 `_json` 数据库列名。

本机数据库迁移前为 `20260914_0052`、`20260918_0108`；执行明确增量后为
`20260914_0052`、`20260923_0114`，新增 `paper_document_parser_runs`、
`paper_document_blocks`、`paper_evidence_locators` 三张表，检查时均为 0 行。
此操作仅新增结构；没有提交、改写或重新解析已有真实论文。

新增 `/api/rag/evidence/region` 返回经过归属校验的当前文件区域。主流程仍保持五阶段，
新增细节只作为 reading_state。用户可显式选择 legacy/text/layout/ocr。默认新链路需要
配置 `UPLOAD_PARSER_QUALITY_REPORT` 指向质量报告，缺失或不达标时拒绝启用。
当前没有实际 50 篇报告，仍以 legacy 为默认，不宣布质量门通过。

仍待验证：原生 PDF LLM、完整 Shadow、真实模型长期行为、完整 MySQL 上传/审核/返修
端到端、浏览器窄屏/键盘操作、Docker 与 50 篇人工标注基准。


### 原生 PDF 适配补充

补充 OpenAI Responses 文件请求与严格 IR 输出测试，校验不完整输出、错误页码、
返回 Claim 代替 IR、非允许供应商/模型等拒绝路径。请求 store=false，不开放工具。
这部分是接口测试，不发送真实文件到供应商；当前服务端没有可用凭据，真实调用仍待验收。


### 最终复核批次

加入原生文件接口拒绝测试和既有来源定位回归后，完整定向批次为 **123 项通过、1 项
跳过**（独立 MySQL 项已另行验证）。随后补充空文本/空表覆盖检查，相关 23 项通过。
区域读取限定原上传者和已批准管理员，返修复用原所有权与版本校验；普通登录用户不能
因此取得他人完整 PDF 页面。强化后的 Claim 校验明确记录规则版本 2。


汇总完整性补充：材料状态的出处不再代替 Tc 结果覆盖；分段识别的不同 Tc、压力或方法
如果在汇总中消失，会以 summary_records_missing 阻止 ready。相关 25 项回归通过。
新方案的分段缓存还纳入请求模型、供应商端点摘要和提示词，避免切换模型后复用旧结果。
原生 PDF 能力与基础契约最后复核 15 项通过；未使用真实供应商凭据。

## 2026-09-24：离线评测工具与详细报告门禁

新增 `pdf_benchmark.py`，读取固定人工标注、两组结果和独立验收 JSON，计算逐论文、
逐类别微平均指标。默认门重算明细并核对文件摘要去重、来源集合、复杂类别召回与
汇总一致性；不接受合成集或仅有汇总数字的早期报告。

运行评测、Evidence 审计、IR 基础契约、上传门禁、上传作业与上传契约六个测试文件，
**122 项通过**。新增测试验证重复预测、错误压力、错文件/页码/引句/区域、整页大框、
失败/漏跑分母、最大匹配顺序无关、非法输入、合成集拒绝、单类别不提升及报告篡改。
CLI 通过真实子进程读取临时 JSON、输出报告并拒绝覆盖输入；不访问供应商或业务库。
已有 spglib/passlib 弃用警告保留。本次只改离线后端工具与门禁，无前端或迁移变更。

这些合成数据仅验证评分算法，未新增真实人工标注论文、未运行真实 50 篇基准，
未完成自动上传运行驱动和输出导出；T002/T030 保持未完成。默认仍为 legacy。

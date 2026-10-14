# 实施计划：MinerU 核心的四工具互补解析

**日期**：2026-10-14。**Issue**：[#136](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/136)。**基线**：[Spec](spec.md) 与已确认的 [四工具架构](four-tool-architecture.md)。

## 范围与技术上下文

用户已明确授权完整接入与测试，DeepSeek thinking 固定关闭。Python 3.12、MinerU 4.0.6 basic OCR 主干、Docling 2.130.0 CPU、Marker 2.0.0 独立环境与本地 llama.cpp、GROBID 0.8.1；前端 React/Vite。复用现有 DocumentIR、上传任务、MySQL 论文/引用/文档来源及 Qdrant 发布入口，不新增数据库表。旧三引擎实验见 validation.md，仅作为反例。

## 组件与职责

- backend/ingest/complementary_pdf.py：唯一解析器 composite；先读取完整 MinerU，按内容信号建立 Docling 表格页和 Marker 公式/OCR/读序页任务，固定原 PDF 哈希及文件身份。
- backend/ingest/complementary_ir.py：保留 MinerU 普通正文；表格优先采用具有更完整行列/单元定位的补强；备选原块及不同数字/符号记录保留。生成一个可校验 IR，并为下游只提供已选内容与必要冲突，避免重复全文膨胀。
- backend/ingest/marker_pdf.py、structured_pdf.py、pdf_parser_worker.py：复用三引擎转换，Marker 从独立解释器执行；补强按页创建临时子 PDF，响应映射回原始页码。保存配置、原始 JSON、stdout/stderr 和运行记录。超时/取消终止本次子进程及其自建子服务。
- backend/ingest/grobid_document.py：一次本机 GROBID 调用得到 header、bibliography 和正文引用锚点；保留 XML 原始制品与 XPath/坐标来源。当前论文 header 与参考文献隔离。不能获得准确页码时明确缺口，不补造页码。
- backend/ingest/upload_jobs.py：新 parser_profile=complementary 使用新适配器，复用 GROBID 引用产物并将正文题录确定性覆盖模型同字段；空字段仍按现有提取补缺并保存来源冲突。科学状态、物性、结构与来源校验仍由既有职责承接。
- backend/rag/llm.py：DeepSeek JSON 请求显式 thinking=disabled；缓存签名包含模式版本，避免复用旧推理配置的结果。
- backend/ingest/domain_extraction.py：按完整页读取紧凑 IR，表格单元不重复序列化；明确标准参数路径、范围使用扩展记录、条件归属检查，不删失败候选换取通过。
- 新任务/API/UI：新 PDF 只有 complementary，TXT/MD/结构附件保留原契约；历史任务由其已保存的 parser_profile 处理，不改变历史 IR。移除上传页方案下拉框。
- 持久化/检索：原始解析、GROBID 结构与补强账本进入任务制品和 document_json；提交后保留文件/页/版本证据；正式发布继续经审核。来源与正文分块继续供当前知识库使用。

## 实施和验证映射

| 来源 | 任务 | 核验 |
| --- | --- | --- |
| FR-013/015、SC-008/010 | T016–T018 | 固定 MinerU 主干；真实四工具；新 API 唯一方案与页面 |
| FR-005/006/017、SC-003/011 | T017/T019 | 按页补强、原页映射、跨文件/表格/冲突保留 |
| FR-007/008/018、SC-002/011 | T019/T020 | 条件错挂反例、来源/范围参数与结构候选、数据库回读 |
| FR-016、SC-009/010 | T018/T019 | 实际模型请求 thinking 关闭；header/参考文献非模型事实 |
| FR-002/010/018、SC-005/010/011 | T020 | H3S 正文/补充、不同论文；原始输出、缺失与故障 |
| FR-012、SC-007 | T021 | Overview/操作说明、自动提交、Issue 验证；远程链接未推送不冒充通过 |

## 依赖与完成门

T016 文档/Issue 更新 → T017 解析与 IR → T018 默认与 GROBID 集成 → T019 契约/来源/表单 → T020 真实运行、故障和持久化 → T021 文档/提交/状态。用户已有实现授权，不重复请求批准常规实现选择。新稳定行为只有实现后才回写 Overview。

普通单元测试验证对齐与契约；实际子进程验证运行/超时/取消；实际本机 GROBID/三引擎和远端 DeepSeek 验证真实 PDF；持久化测试覆盖事务和版本回读。Mock 不能代替核心引擎或数据库测试。闭环未完成时保留对应 Tasks 未勾选，并记录具体边界。

## 必要复杂度

Marker 的 NumPy/Pillow 依赖与主后端不同，使用独立运行环境；不复制整个上传系统。原始备选与紧凑读取分开，避免来源丢失和上下文膨胀。GROBID 题录、引用边与科学值各有唯一事实来源，避免由模型自由生成不可核验关系。

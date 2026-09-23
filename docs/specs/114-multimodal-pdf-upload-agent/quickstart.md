# 快速验收：多模态 PDF 解析与证据驱动上传 Agent

**GitHub Issue**：[ #114](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/114)

## 前置条件

- 当前分支为 `mayuan`。
- Python 依赖、MySQL、Redis、RQ 和现有 LLM 配置已准备。
- 若没有 GPU 或视觉模型，使用 fallback 测试；不把缺 GPU 当作失败。
- 评测论文目录和人工标注索引由 T003 提供。

## 自动化验证

```bash
python -m pytest -q tests/01_decentralized_uploading/test_issue114_multimodal_pdf_agent.py
python -m pytest -q backend/tests/test_upload_jobs.py backend/tests/test_upload_workflow.py
python -m pytest -q tests/01_decentralized_uploading/test_scientific_evidence.py
```

数据库迁移和真实 SQLite/隔离 MySQL 验收按项目既有迁移脚本执行；不得把静态 Schema 检查作为迁移完成证明。

## 端到端步骤

1. 准备一篇数字双栏论文、一篇扫描论文、一篇包含多页表格和公式的论文，另附一份补充材料。
2. 创建一个正文 + 补充材料的上传任务，观察 `extracting → reading → summarizing` 状态。
3. 确认任务生成 Document IR：文件身份、PDF 页码、块类型、坐标、内容哈希和解析器版本可见。
4. 确认 Tc、压力、方法和条件 Claim 都能定位到块、表格单元或 OCR 区域。
5. 让测试适配器返回无法定位的 quote，确认该 Claim 被标记为 `uncertain/rejected`，不会进入正式科学字段。
6. 禁用 Docling/MinerU 或视觉能力，确认任务记录降级原因并仍可通过 PyMuPDF 进入人工处理/旧链路。
7. 在 Shadow 模式下确认用户草稿仍来自旧链路，新链路结果只用于比较；在灰度失败场景确认回退旧链路。
8. 打开校对页字段证据，确认页码、区域高亮、原文引句和渲染失败降级提示。
9. 提交待审核并生成论文 revision，确认文档定位随 revision 复制，删除/回滚不留下孤立定位。
10. 使用旧缓存和没有 bbox 的历史 Evidence 打开页面，确认仍显示页码和引句。

## 基准验收

对至少 50 篇标注论文分别记录：关键记录 Precision/Recall/F1、条件关联准确率、Evidence 定位率、漏记录率、无依据字段率、人工修改量、处理时延、Token、CPU/GPU 时间和成本。新链路只有在 SC-001～SC-008 全部满足时才能切换默认。

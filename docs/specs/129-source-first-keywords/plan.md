# 实施计划

**输入**：[规格](spec.md)、[研究](research.md)、[数据模型](data-model.md)、[契约](contracts/keywords.md)、[任务](tasks.md)。

## 技术上下文

上传 Worker 在 `backend/ingest/upload_jobs.py` 中保存每份 PDF/TXT/MD 的 Markdown，进行分段阅读、全文汇总、草稿归一化和来源核对。来源定位复用 `backend/ingest/property_evidence.py` 的 `source_chunks`/`locate`；上传与审核共享 `backend/ingest/scientific_evidence.py` 的字段记录。`paper.keywords_tags` 是现有数组，无需数据库迁移。

## 实施顺序

1. 增加独立关键词选择器：先查主文明确关键词栏并逐字定位；没有可靠列表才按正文窗口全文提炼。每个窗口都需成功阅读，失败返回空值和状态，不使用旧摘要补全路径冒充全文。
2. 在草稿汇总完成后覆盖旧关键词生成值，保存服务端来源分析；仅作者原列允许保留中文。草稿 PUT 继续由服务端维护分析，人工改值后不复用分析。
3. 将来源分析接入关键词字段核对与侧栏，展示作者原列或全文提炼，并为审核重读保留来源类别。其他叙述字段仍沿用现有规则。
4. 用真实解析正文夹具和上传草稿核对路径验证短文、长文、中文、失败、多文件和修改失效；通过后更新 Overview 和 Issue。

## 质量门

遵守 `AGENTS.md` 的 `mayuan` 分支、隔离暂存与自动提交要求。当前工作区已有其他任务改动，涉及共享文件时只提交本 Feature 新增的精确补丁。代码职责保持单一：关键词选择器决定词和来源；上传 Worker 只调用；核对层只验证并展示来源。

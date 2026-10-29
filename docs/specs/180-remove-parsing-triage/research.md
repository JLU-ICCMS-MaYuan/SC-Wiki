# 实施依赖调查

## 问题归属

本次属于原设计偏离：#172 将排查方式扩展成独立分类产品。按 #180 撤销该分支，不修改科学提取、数据所有权或审核标准。

## 删除边界

- `backend/ingest/parsing_diagnostics.py` 仅服务分类、责任状态、影响分组及分类用原 PDF 扫描；其唯一正常生产调用在 `upload_jobs.py` 的字段建议完成后、最终保存前。删除模块和该调用，不动前面的解析原文账本生成及后面的草稿锁／持久化。
- `ParsingDiagnosticsPanel.tsx`、`lib/parsingDiagnostics.ts` 仅服务独立入口、侧栏、分组和快照。删除它们及 UploadTaskEditor 的接线；不恢复此前逐条长警告。
- `rebuild-parsing-diagnostics.py` 是分类专用重建工具，删除。`verify-bibliography-parsing.py` 同时验证题录，保留主流程并移除分类步骤。
- 专用测试不再要求组件和分类算法存在。原测试文件中的出版年份、身份及 PDF 下载日期回归迁入独立题录测试，不能整包丢掉。

## 保留与历史兼容

`complementary_ir.py` 和 `grobid_document.py` 的原始差异、`publication_year.py`、声子方法及 Tc 配对不变。`parsing_conflicts` / `bibliography_conflicts` 继续作为原始账本随草稿存取；历史条目中的未知 `triage` 原样保存，不读取它来触发计算。前端保留宽容的账本数据类型，不再承载派生分类类型或任何状态机。

## 并行边界

实施前已保存工作区及索引差异到 `/tmp/scwiki-180-baseline/`。`upload_jobs.py` 与两份 upload 翻译含其他任务改动；最终从原基线逐块提取本次增量，候选提交在独立临时目录运行，不覆盖共享工作树或其他任务索引。

## 取舍

不保留隐藏分类服务、不建立新面板、不清洗旧字段，也不补做已排除的47项旧清单。删除仅在字段提取完成之后的派生链，因此不改变提取提示、输入、归一化或题录选择；验证实际 Worker 保存路径与保留字段回归，不为本次虚构源头模型重提结果。

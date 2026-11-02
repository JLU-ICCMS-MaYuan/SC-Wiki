# 值没变，为何要求理由并展示旧整条原文？

2026-11-02 只读调查，解释同一 q 网格的两个现象；方案未实施。

**结论：值没有因这次保存改变；内部编号变化被误记成新增，字段引句也未正确拆给子项。**

## 事实与原因

本机 MySQL `127.0.0.1:3307/scwiki` 的上传任务 `5dab6b2fb9fa46998f180d71c3742d43`，150 GPa、235 K 记录：

- 07:25:29 的基线把旧键 `877f5e42…` 记为删除、新键 `99fe2302…` 记为新增；两边值都是 `12×12×12`。内存副本仅去掉 `field_key` 就重现旧键。应用设置会补此编号，审核身份却从原 `key` 切到它，于是比较“空→12×12×12”。这不能证明用户改过值，其他子项须分别判断。
- 当前引句 0 条，整条参考 7 条，其中已有标到 `extensions.1.value_raw` 的 SI 第 3 页引句。代码匹配对象地址 `extensions.1`，漏掉叶子地址，只留整条参考；前端遂显示“未找到依据”和“旧整条记录原文”。“旧”指绑定范围，不表示论文过时。

## 约束与拟议处理

功能路径：上传草稿→计算条件设置→字段身份／修改基线→来源拆分→侧栏审核。

[#147](../../specs/147-two-stage-field-review/approval-submit-consistency.md)要求未改值无需理由；[#109](../../specs/109-field-evidence-and-ai-suggestions/spec.md)要求稳定身份与明确来源。建议补号保持身份和基线；叶子引句核验后归位，无归属原文仅作参考，不复制整条旧通过。真实改值仍执行原门禁；污染基线修正另定范围。

![当前流程与拟议修复](identity-and-source.svg)

核验：只读重建详情、内存复算身份，图已渲染；未写业务数据或调用模型。

依据：[补号](../../../frontend/src/components/CalculationConditionFields.tsx)、[身份与拆分](../../../backend/ingest/property_field_review.py)、[修改比较](../../../backend/ingest/field_review.py)、[侧栏](../../../frontend/src/components/EvidenceWorkflow.tsx)。下一步讨论是否按上述边界进入 Issue／Spec。

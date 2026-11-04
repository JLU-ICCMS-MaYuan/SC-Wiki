# 实施任务

输入：[spec.md](spec.md)、[plan.md](plan.md)、[research.md](research.md)、[data-model.md](data-model.md)、[契约](contracts/filling.md)。

- [x] T001 创建 #176、保存完整规格与原图，检查文档与既有依赖。
- [x] T002 [US1] 在 tests/01_decentralized_uploading/predicted-tc-groups.test.tsx 增加文本错误固定布局、other 与方法限制反例。
- [x] T003 [US2] 在 tests/01_decentralized_uploading/test_scientific_form_filling.py 增加真实四记录重放、候选丢失、来源、补全、多方法及其他物性反例。
- [x] T004 [US1] 修改 frontend/src/lib/predictedTcGroups.ts、PredictedTcGroupEditor.tsx，恢复固定布局及 other 保存。
- [x] T005 [US2] 实现 backend/ingest/scientific_form_filling.py，模型语义整理、候选去向和读源循环。
- [x] T006 [US3] 在 backend/ingest/upload_jobs.py 接入正式路径，调整提示词边界及端点等价防遗漏，保存原始响应和诊断。
- [x] T007 [US1] 扩展完整宿主与保存重读回归，执行两条表单契约检查、受影响回归及构建。
- [x] T008 [US4] 原 PDF／SI 定向真实重新提取、正式整理与隔离保存，覆盖 Tc 及相邻科学字段，记录模型与来源版本。
- [x] T009 使用 Overview Skill 回写已验证事实、README 操作、验证报告及 Issue，精确提交本次文件。

T001 后先完成 T002、T003 的失败证据，再实施 T004—T006。T007、T008 通过才完成 T009；远程链接未验证不关闭 Issue。

## 2026-11-03 实现补齐

- [x] T010 [US2] 保存H3S真实失败响应，先重现概述归并被拒，再登记显式对应协议并补齐守恒及来源边界；固定重放、真实模型整理、原PDF块重新AI提取及正式后续规范化、隔离保存重读均完成。独立投影77项后端／工具、132项表单及8项变异检出通过；验证范围和完整网页未完成项见validation.md。

- [x] T011 按2026-11-04用户确认集中重复候选证据、剔除已读目录重复项并实测真实发送字符串；先保存失败回归，再验证原候选和不同来源身份不变。测量及检查范围见validation.md。
- [ ] T012 完成La-H原文新上传、送审、退回返修、批准及探索与正式数据核验；网页未完成前不以局部通过代替。

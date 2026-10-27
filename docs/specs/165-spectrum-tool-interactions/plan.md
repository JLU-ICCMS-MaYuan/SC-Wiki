# 实施计划：谱线编辑器双拖动按钮与工具交互

**Issue**：[#165](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/165)
**日期**：2026-10-27
**Spec**：[spec.md](spec.md)
**阶段边界**：本轮只交付计划，不执行以下代码修改。

## 摘要

将两个拖动按钮直接作为互斥工具入口，加入无激活工具状态。编辑器统一切换/退出操作，画布复用真实连线与吸附算法；起点选择不写曲线。工具样式由主题提供并限定作用范围。

## 技术上下文

- 语言：TypeScript ~5.6、React 19；前端Vite 5.4、MUI 7.3。
- 目标：正式 SpectrumManualEditor，覆盖 α²F/DOS、桌面/窄屏及横/纵频率轴。
- 存储：沿用编辑器 Document/History 和现有正式保存接口，不新增数据库字段。
- 测试：Vitest/Testing Library（tests/01_decentralized_uploading）、隔离Playwright正式页面与HTTP后端。
- 性能：复用单次线性吸附搜索及拖动开始时的权重准备，不改变算法复杂度。
- 约束：mayuan分支，保护已有两个dragInfluence.ts改动，独立Demo不修改；当前无实施、推送、部署授权。

## 质量门

| 来源 | 要求 | 当前结论 |
|---|---|---|
| 用户最终需求 | 两个并列按钮，浅/深色统一 | Spec FR-001/009与交互契约一致 |
| 用户范围澄清 | 仅持续工具切换 | FR-007/008区分工具与立即动作 |
| 仓库 | 保护无关工作、文档中文 | 本轮仅新Spec目录；不暂存既有参数文件 |
| 总览/#161 | 真实连线、两种加点能力、版本权限 | 复用实现，不重新定义数学或保存 |
| 技能 | 文档先行、已确认需求 | Spec记录完整原话和最终批准 |
| 关闭门 | 远程Spec链接可访问 | 未推送，保持未完成，不阻止此次本地文档交付 |

## 文档结构

本目录：spec.md、plan.md、research.md、data-model.md、contracts/interactions.md、quickstart.md、tasks.md、checklists/requirements.md、analysis.md。

## 源码触点（计划）

- frontend/src/components/spectrumEditor/SpectrumManualEditor.tsx：统一工具选择、两个按钮、移除重复开关、退出回调。
- frontend/src/components/spectrumEditor/SourceCanvas.tsx：无工具只选点、等待起点、退出清理、候选提示。
- frontend/src/components/spectrumEditor/styles.css：持续工具专用浅/深样式，避免改变所有.active元素。
- frontend/src/theme.ts：只读颜色事实来源；实现时使用主题token，不复制另一套色值。
- frontend/src/components/spectrumEditor/engine.ts：复用prepareMove、snapTarget、appendPoint、insertDrawnPoints、joinExistingPoint，不改联动数值。
- tests/01_decentralized_uploading/spectrum-tool-interactions.test.tsx：新增工具交互测试。
- tests/01_decentralized_uploading/spectrum-tool-interactions-production.cjs：新增隔离浏览器验证，复用现有测试服务。

结构选择：状态由Editor管理，Canvas负责手势，engine负责既有数据编辑。工具切换不能调用曲线保存或改变Document；不新增重复算法或业务状态表。

## 需求到设计与验证映射

| 来源 | 设计/事实来源 | 任务 | 验证 |
|---|---|---|---|
| FR-001、SC-001、US1 | Editor双按钮，Canvas派生linked，prepareMove | T002–T004 | 单点不牵连、联动权重原样 |
| FR-004/005/006、SC-002/004/005、US2 | snapTarget 8屏幕像素及既有增点/插入/补接 | T005/T006/T009 | 首次只选起点、缩放、旧连线回归 |
| FR-002/003/007/008、SC-003、US3 | idle及统一工具切换、Canvas清理 | T002/T003/T007 | 同钮退出、工具互斥、Esc、无残留 |
| FR-009、SC-006、US3 | 主题token、工具专用选择器、aria-pressed | T007/T008/T009 | 计算样式/悬停/键盘/窄屏截图 |
| SC-004/005 | 正式保存接口和隔离夹具 | T009 | α²F/DOS保存刷新、撤销、版本 |
| 全部 | 文档与当前总览 | T001/T010 | 原文/追踪/链接检查及事实回写 |

## 阶段与依赖

T001完成文档；后续获实施指令后执行T002基础测试、T003统一工具状态，再按US1/US2/US3展开，最终T009集成验证与T010回写。共享文件串行修改。

## 必要复杂度

加入无激活工具状态使“再点退出”成为真实行为；只取消按钮高亮仍会误拖动。标定取点身份包含轴和刻度槽，不能只比较calibrate字符串。吸附预览与起点点击分离，防止选择已有点时重复生成点。按钮浅/深样式限定工具控件，避免影响曲线选择和立即动作。

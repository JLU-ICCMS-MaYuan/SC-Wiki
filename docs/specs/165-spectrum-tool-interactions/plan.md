# 实施计划：谱线人工调整工具与界面交互

**Issue**：[#165](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/165)
**日期**：2026-10-27；**更新**：2026-11-05
**Spec**：[spec.md](spec.md)
**阶段边界**：文档交付后用户明确要求“开始”，本轮执行以下已确认计划。

## 摘要

六工具共用互斥入口和快捷键映射，左侧竖排并将不透明度下置；显示开关由Editor注入Canvas工具栏，坐标区精简，方向和多曲线操作按用户答复保留。沿用idle、真实连线、吸附与撤销保存；工具样式继续读取站点主题。

## 技术上下文

- 语言：TypeScript ~5.6、React 19；前端Vite 5.4、MUI 7.3。
- 目标：正式 SpectrumManualEditor，覆盖 α²F/DOS、桌面/窄屏及横/纵频率轴。
- 存储：沿用编辑器 Document/History 和现有正式保存接口，不新增数据库字段。
- 测试：Vitest/Testing Library（tests/01_decentralized_uploading）、隔离Playwright正式页面与HTTP后端。
- 性能：复用单次线性吸附搜索及拖动开始时的权重准备，不改变算法复杂度。
- 约束：mayuan分支，保护无关工作区修改与两个dragInfluence.ts，独立Demo不修改；实施已获授权，未授权推送或部署。

## 质量门

| 来源 | 要求 | 当前结论 |
|---|---|---|
| 用户最终需求 | 六工具竖排、快捷键、浅/深色统一 | FR-001/009/010/011 |
| 用户范围澄清 | 仅持续工具切换 | FR-007/008区分工具与立即动作 |
| 仓库 | 保护无关工作、文档中文 | 本轮仅谱编辑器及其需求和回归；不暂存其他任务文件 |
| 总览/#161 | 真实连线、两种加点能力、版本权限 | 复用实现，不重新定义数学或保存 |
| 技能 | 文档先行、已确认需求 | Spec记录完整原话和最终批准 |
| 关闭门 | 远程Spec链接可访问 | 未推送，保持未完成，不阻止此次本地文档交付 |

## 文档结构

本目录：spec.md、plan.md、research.md、data-model.md、contracts/interactions.md、quickstart.md、tasks.md、checklists/requirements.md、analysis.md。

## 源码触点

- frontend/src/components/spectrumEditor/SpectrumManualEditor.tsx：六工具、快捷键、方向与曲线区条件显示、坐标区及退出回调。
- frontend/src/components/spectrumEditor/SourceCanvas.tsx：select只选点、工具栏显示控件槽、等待起点、退出清理及候选提示。
- frontend/src/components/spectrumEditor/styles.css：左侧竖排、滑条下置和窄屏布局，工具浅/深样式保持局部。
- frontend/src/theme.ts：只读颜色事实来源；实现时使用主题token，不复制另一套色值。
- frontend/src/components/spectrumEditor/engine.ts：复用prepareMove、snapTarget、appendPoint、insertDrawnPoints、joinExistingPoint，不改联动数值。
- tests/01_decentralized_uploading/spectrum-tool-interactions.test.tsx：新增工具交互测试。
- tests/01_decentralized_uploading/spectrum-tool-interactions-production.cjs：新增隔离浏览器验证，复用现有测试服务。

结构选择：状态由Editor管理，Canvas负责手势，engine负责既有数据编辑。工具切换不能调用曲线保存或改变Document；不新增重复算法或业务状态表。

## 需求到设计与验证映射

| 来源 | 设计/事实来源 | 任务 | 验证 |
|---|---|---|---|
| FR-001、SC-001、US1 | Editor独立拖动按钮，Canvas派生linked，prepareMove | T002–T004 | 单点不牵连、联动权重原样 |
| FR-004/005/006、SC-002/004/005、US2 | snapTarget 8屏幕像素及既有增点/插入/补接 | T005/T006/T009 | 首次只选起点、缩放、旧连线回归 |
| FR-002/003/007/008、SC-003、US3 | idle及统一工具切换、Canvas清理 | T002/T003/T007 | 同钮退出、工具互斥、Esc、无残留 |
| FR-009、SC-006、US3 | 主题token、工具专用选择器、aria-pressed | T007/T008/T009 | 计算样式/悬停/键盘/窄屏截图 |
| SC-004/005 | 正式保存接口和隔离夹具 | T009 | α²F/DOS保存刷新、撤销、版本 |
| 全部 | 文档与当前总览 | T001/T010 | 原文/追踪/链接检查及事实回写 |

## 阶段与依赖

T001完成文档；后续获实施指令后执行T002基础测试、T003统一工具状态，再按US1/US2/US3展开，最终T009集成验证与T010回写。共享文件串行修改。

## 必要复杂度

加入无激活工具状态使“再点退出”成为真实行为；只取消按钮高亮仍会误拖动。标定取点身份包含轴和刻度槽，不能只比较calibrate字符串。吸附预览与起点点击分离，防止选择已有点时重复生成点。按钮浅/深样式限定工具控件，避免影响曲线选择和立即动作。

## 2026-11-05 界面调整

- Editor 持有六工具列表，按列表生成按钮和 Alt+1～6 映射；Canvas 新增 select 身份，复用现有只选不拖路径。快捷键用 KeyboardEvent.code 识别物理数字键，避免 macOS Option 特殊字符；重复快捷键维持选中，鼠标反选仍退出。输入框内 Alt 数字可切工具，组合输入不拦截；保存、离开确认期间屏蔽。
- 工具列和不透明度共用左侧容器，按钮在上、滑条在下；窄屏保留竖排，工具列可独立滚动。
- Canvas 提供可选 toolbarControls 槽，由 Editor 注入分波与原图开关，紧靠适应窗口左侧；详情不传时布局及行为保持。
- PointForm 删除像素读数和状态说明，保留换算数据来源 doc.calibration，确认按钮仅改标签；点坐标及保存所有权不变。
- 用户明确保留方向切换并隐藏联动说明；仅 doc.curves.length > 1 时展示编辑曲线区。方向状态仍由 Editor 持有，Canvas 消费，顶部分波切换和未保存确认保持。

| 来源 | 数据事实与职责 | 任务 | 验证 |
| --- | --- | --- | --- |
| FR-001/010/011、SC-007 | Editor 工具顺序、Canvas 选点和导航；Document 不变 | T011/T012 | 六工具/快捷键/选点隔离、桌面及窄屏实测 |
| FR-012、SC-008 | Editor 显示状态、Canvas 工具栏槽 | T012/T014 | 开关位置及渲染与不透明度禁用 |
| FR-014、SC-009 | Editor dragMode/active 与 doc.curves | T013/T014 | 方向限制、单曲线隐藏及多曲线切换 |
| FR-013、SC-008 | PointForm、doc.calibration、既有 change/save | T013/T014 | 坐标确认、撤销、保存回读 |

仅影响独立谱编辑器 UI。科学表单键、PDF/AI 提取、engine 算法、联动参数、正式保存接口不变。按仓库规则执行 form-contract 与 mutation 及谱线回归；未推送不声称远端CI验收。

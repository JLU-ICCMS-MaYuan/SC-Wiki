# 实施计划

2026-10-28；[#174](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/174)；[Spec](spec.md)。

## 技术上下文与范围

React 19、TypeScript 5.6、MUI 7、Vite 5、Vitest 2、Playwright。沿用现有草稿、字段保存器、核对结果和 SQL/Redis 契约，不变更后端。只修改科学表单共享更新路径；其他入口登记适用规则和未验证边界。工作基线 d8e42242，保留其他任务改动。

## 设计与职责

1. MaterialStatesEditor 保留卡片缓存；共享目录、语言、只读仍是公共依赖，问题路径和错误按卡片作用域比较内容。当前卡片的临时输入、结构候选等变化只失效本卡。缓存事件通过最新回调读取当前草稿，不能捕获过期宿主状态。
2. EvidenceFieldMarkers 将节点拓扑定位与核对结果更新分开。结构/身份变化才重新查找；单字段值、状态或理由变化复用已找到的节点并更新相应记录。占位入口打开时读取最新控件值。标记自身 DOM 变化不引发无休止重新定位。
3. PropertySpectraProvider 稳定未变化的共享上下文，最新 beforeNavigate 通过稳定包装回调读取，不能冻结旧草稿；真实谱列表、状态身份或权限变化仍通知消费者。
4. 保留 ReviewPaperTextField 当前受控输入与保存契约，不为提速改变自动保存时机、失焦语义或模型触发。
   EvidenceWorkflow 的编辑标记只读取本次明确受影响的字段；状态/模块/记录集合结构变化时仍全量重新定位。保留未变化记录对象，避免一次输入让全部标记消费者更新。
5. 在 AGENTS.md 写入适用约束和必跑检查；提供 npm 本地脚本与 pull_request CI 工作流。测试注入回退通过独立 Vite 转换执行，不能修改实际工作树。远端保护与运行状态不冒称已配置或已通过。

## 质量门

Spec 已确认；执行前复核 mayuan。文件级确认并行工作不覆盖。先完整宿主失败测试，再修改代码、回归和浏览器对照。远程 Spec 链接待推送验证，不因此自行推送。

## 结构与映射

| FR/SC | 组件职责／数据来源 | 任务 | 验证 |
| --- | --- | --- | --- |
| FR-001/002，SC-001/004 | 卡片缓存、来源标记、谱上下文；当前草稿与核对记录 | T002–T004 | 四宿主渲染计数、大草稿浏览器 |
| FR-003/005/006，SC-002 | 原输入、稳定身份、最新宿主回调 | T002–T004 | 输入法、错误、删除、侧栏、冲突 |
| FR-004，SC-003 | 既有字段保存器与审核 Hook | T004 | 无改零写、保存重载及模型请求计数 |
| FR-007/008，SC-005 | AGENTS、npm、CI 与回退注入脚本 | T005 | 正常通过，缺陷注入失败 |
| FR-009，SC-006 | form-inventory.md 与现有路由 | T006 | 入口覆盖及未验证状态核查 |

产物：spec、plan、research、data-model、contracts/ui、tasks、quickstart、form-inventory、validation 及检查表。实现文件为 frontend/src/components/{MaterialStatesEditor,EvidenceFieldMarkers,EvidenceWorkflow,PropertySpectra}.tsx；测试位于 tests/01_decentralized_uploading；门禁入口为 scripts/check-form-contract.mjs、frontend/package.json 和 .github/workflows/form-contract.yml。

## 顺序与回滚

T001 文档 → T002 失败测试 → T003 实现 → T004 验证 → T005 门禁 → T006 文档及任务独立提交。必要复杂度限于实际依赖与节点绑定；不引入新状态库、虚拟化框架或另一个持久值源。回滚本次前端提交即可，不涉及迁移或用户数据回填。

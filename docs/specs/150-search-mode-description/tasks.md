# 实施任务：检索方案说明

**输入**：[Spec](spec.md)、[Plan](plan.md)、[Research](research.md)、[界面契约](contracts/ui.md)。

## 阶段 1：准备与基础

- [x] T001 核对既有 Go/Python 匹配逻辑，完成 docs/specs/150-search-mode-description/ 文档、图片归档与需求检查；证据见 research.md、spec.md 图片索引及 requirements.md，远程链接仍单独未完成。

## 阶段 2：US1——选择方案时理解匹配范围（P1，MVP）

- [x] T002 [US1] 在 frontend/src/i18n/zh/search.ts 与 frontend/src/i18n/en/search.ts 添加对应说明；浏览器逐条核对两种语言的三种说明通过。
- [x] T003 [US1] 在 frontend/src/pages/SearchPage.tsx 共用选项列表，派生当前说明并实现卡片头部响应式布局；37 组真实布局检查通过，见 quickstart.md。

独立验收：进入 /search，空选择时切换三个选项、中英文，核对说明和位置；选择 La/H 后清除或进入结果页。

## 阶段 3：验证与收尾

- [x] T004 按 docs/specs/150-search-mode-description/quickstart.md 验证真实页面交互与布局、运行既有检索回归和构建，回写证据；本次功能验收与构建通过，回归中 3 项基线失败已对照并明确记录，不代表全套测试通过。
- [x] T005 使用总览维护 Skill 更新 docs/overview/03_Superconductivity_Data_Search_and_Database_Discovery/local-material-search.md，并核对本次 diff 与文档；仅记录已落地说明行为及其边界。

## 依赖、覆盖与交付

按 T001 → T002 → T003 → T004 → T005 串行完成；两份字典可独立修改，但本次无需并行代理。唯一故事即 MVP，无额外增量。

| 来源 | 任务 | 验证 |
| --- | --- | --- |
| FR-001 / SC-002 | T003、T004 | 桌面与窄屏布局 |
| FR-002 / SC-001 | T001–T004 | 三种说明与实际规则一致 |
| FR-003 / 场景 1–3 | T003、T004 | 默认、空选择、清除 |
| FR-004 / 场景 4 | T002–T004 | 语言切换与换行 |
| SC-003 | T004 | 选择、清除与结果请求参数 |

未完成协作行动仅以 GitHub Issue 为准。远程 Spec 链接待推送后核验；不擅自推送或关闭 Issue。

## 阶段 4：布局修订收敛

来源：用户在 IMG-002 后明确要求替换初版头部布局；旧 T003/T004 的证据仅对应旧版，不能证明新布局完成。

- [x] T006 [US1] 更新 docs/specs/150-search-mode-description/spec.md、plan.md、research.md、contracts/ui.md、checklists/requirements.md，归档 IMG-002 并将最新原话同步到 Issue #150；覆盖 FR-005–007。
- [x] T007 [US1] 修改 frontend/src/pages/SearchPage.tsx 为首行对齐、已选元素独立下一行、统一字号和说明弹性列；覆盖 FR-005–007。
- [x] T008 [US1] 按 docs/specs/150-search-mode-description/quickstart.md 复验双语桌面/窄屏、字号/中心/列宽及选择交互，记录截图并同步 docs/overview/03_Superconductivity_Data_Search_and_Database_Discovery/local-material-search.md；覆盖 SC-001–004。

按 T006 → T007 → T008 串行执行，原任务与历史验收保留。

本轮 T006–T008 证据：spec.md 原文及 IMG-002 索引、quickstart.md 当前版本验收、assets/aligned-validation.json 和新版截图；43 组界面检查及修订后的构建通过。

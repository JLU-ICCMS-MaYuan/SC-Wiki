# 实施任务：材料家族论文统计

输入：[规格](spec.md)、[计划](plan.md)、[研究](research.md)、[数据](data-model.md)、[契约](contracts/publication-stats.md)。

## 阶段 1：准备

- [x] T001 完成 `docs/specs/115-material-family-publication-stats/` 全部产物及需求一致性检查，建立 Issue 双向关联。

## 阶段 2：基础与 US1（P1、MVP）

- [x] T002 [US1] 在 `goserver/handlers/publication_stats_test.go` 编写实际 SQL 聚合、版本边界、年份、HTTP 缓存与失败测试。
- [x] T003 [US1] 在 `tests/07_researcher_community_forum/publication-stats.test.tsx` 编写柱图、空态、刷新、错误、双语及页面集成测试。
- [x] T004 [US1] 在 `goserver/handlers/publication_stats.go` 实现聚合快照与 HTTP，在 `goserver/main.go` 注册公开路由。

## 阶段 3：US2 与 UI（P1）

- [x] T005 [US2] 在 `frontend/src/components/community/PublicationStats.tsx` 实现双柱图、选择和刷新，在 `frontend/src/pages/share.tsx` 接入，并扩展 `frontend/src/i18n/zh/share.ts` 和 `frontend/src/i18n/en/share.ts`。

## 阶段 4：验证与收尾

- [x] T006 使用 `scripts/run_issue115_integration.py` 及 `docs/specs/115-material-family-publication-stats/quickstart.md` 验证 API、UI、构建及相关回归，记录证据。
- [x] T007 回写 `docs/overview/06_Researcher_Community_Forum/researcher-contribution-ranking.md` 及导航，更新本目录验证结果并仅提交本次文件。

## 覆盖、依赖与独立验收

T001 → T002/T003 → T004 → T005 → T006 → T007。US1 单独核对目录及去重总量；US2 依赖同一统计快照，以展开、切换、关闭和年度守恒验收。测试任务运行成功后才勾选。无并行代理任务。

FR-001/002、SC-001 对应 T002/T004；FR-003/004、SC-002 对应 T002/T003/T005；FR-005/006/007、SC-003 对应 T002–T006。范围和异常场景均有覆盖，无新增范围。

## 验证证据与交付边界

T001–T007 的证据见 [quickstart.md](quickstart.md)。Issue 已反向关联 Spec 并记录本地验收结果；远端文档链接需要推送后才可访问，因此 Issue 保持开放。已执行需求、代码及验收对照，无需追加收敛任务。代码提交不包含 #114 或其他已有改动，未执行推送或部署。

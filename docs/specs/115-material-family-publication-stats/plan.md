# 实施计划：材料家族论文统计

**Issue**：[ #115](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/115) · **日期**：2026-09-24 · **规格**：[spec.md](spec.md)

## 技术上下文与方案

Go 1.25、Gin、GORM、MySQL、Redis；React 19、TypeScript 5.6、MUI 7。复用已有库，不增加依赖或迁移。

新增公开 `GET /api/community/publication-stats`。单条 SQL 将目录左关联按当前版本、已批准论文去重聚合的家族/年份计数，合并未分类计数。单语句数据库快照保证总量与年度一致；服务端补零、稳定排序并缓存一小时。Redis 失败直接查询数据库，数据库失败返回 500，不缓存部分结果。

`goserver/handlers/publication_stats.go` 负责聚合与 HTTP；`goserver/main.go` 注册路由；不扩展用户贡献接口，避免耦合用户身份与论文统计。

`frontend/src/components/community/PublicationStats.tsx` 负责独立快照加载、小时定时器及柱图。`share.tsx` 在贡献榜后挂载组件，现有刷新按钮同时触发新组件刷新；组件内也提供刷新/重试。用 MUI/CSS 渲染有统一纵轴比例的竖柱图，家族整列为原生按钮（含零篇），年度柱为非交互展示；无需新增图表依赖或绘制抽象层。类别过多时只在图表内部滚动。现有双语字典扩展文案。

使用请求序号丢弃过期响应、卸载后结果；总量和展开区从同一状态对象派生。刷新保留选中 ID，目录删除该 ID 后展开区自动消失。

## 质量门

| 来源 | 要求 | 满足方式 |
| --- | --- | --- |
| AGENTS.md | mayuan 分支、独立提交范围 | 每次写入及提交前核验，保留 #114 改动 |
| Issue #115 | 家族去重、年度一致 | 单 SQL 聚合与真实数据库测试 |
| Overview | 当前版本、已批准公开边界 | 在论文及关联处限制版本及状态 |
| Spec | 可访问、异常、刷新、回归 | 原生按钮、组件及页面行为测试 |

## 需求到实现和任务映射

| 来源 | 数据事实来源与职责 | 任务 | 验证 |
| --- | --- | --- | --- |
| US1、FR-001/002、SC-001 | papers、paper_material_families、material_families → 聚合接口 | T002–T004 | 隔离 MySQL 实际 SQL 和 HTTP；SQLite 可用于有 C 编译器的环境 |
| US2、FR-003/004、SC-002 | 聚合接口年度数组 → 柱图 | T002–T005 | 去重、补零、未知年份、点击切换收起 |
| FR-005/006/007、SC-003 | Redis 完整快照 → React 状态及现有页面 | T003–T006 | 缓存 TTL/强刷/失败、匿名页面、定时器、中英和贡献榜回归 |

## 阶段与依赖

先完成全部设计及质量检查，再写测试、后端和 UI，最后验证、文档回写与提交。`scripts/run_issue115_integration.py` 自动创建和清理隔离 MySQL，并可启动浏览器夹具。MVP 为 US1，US2 使用同一快照；无需并行代理。详见 [tasks.md](tasks.md)。

## 文档

[研究决策](research.md)、[数据模型](data-model.md)、[接口契约](contracts/publication-stats.md)、[验证路径](quickstart.md)、[需求检查](checklists/requirements.md)。

## 一致性检查结论

需求检查 8/8 通过，FR-001–FR-007 与 SC-001–SC-003 均有设计、任务及测试映射。无 CRITICAL/HIGH 冲突，无数据迁移及新增依赖。实现完成后复核未发现遗漏或未授权能力；验证证据见 [quickstart.md](quickstart.md)。

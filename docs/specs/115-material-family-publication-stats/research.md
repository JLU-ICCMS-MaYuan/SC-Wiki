# 技术决策

## 聚合口径

决策：以 `papers.review_status = approved` 和 `paper_material_families.paper_revision = papers.content_revision` 为准，每个家族与年份 `COUNT(DISTINCT papers.id)`。
理由：与现有社区图表公开边界一致，论文计数不因物性条数膨胀。
备选：从 Tc 点聚合会漏掉无 Tc 的论文，已拒绝。
证据：`goserver/handlers/stats.go`、`goserver/models/models.go`。

## 一致快照与缓存

决策：单条含目录左关联及未分类分支的 SQL；总数从同一批年度聚合行累加；Redis 独立键缓存一小时，强刷绕过缓存，互斥重建。
理由：避免多次查询或多个接口在审核变更期间出现总量与年度不一致。
备选：分开请求总量和明细增加一致性负担；数据库迁移或长期统计表超出需要。

## 年份与展示

决策：复用管理员 1–9999 年约束，无效年份折叠为未知；服务端补零。家族 ID 0 代表未分类，真实目录 ID 保持原值。同量按 ID 稳定排序。
理由：已有校验可复用，前端只展示而不建立第二套统计口径。
证据：`goserver/handlers/admin.go` 的年份校验、`frontend/src/lib/scatterConfig.ts` 的未分类 ID。

## 前端职责

决策：新组件独立持有统计快照及请求生命周期；页面仅转发手动刷新信号。原生按钮/CSS 竖柱保留数值比例、坐标标签及键盘交互，长序列内部滚动。所有展示名称复用 `familyName` 的中英回退。
理由：避免把新聚合生命周期加入已较大的页面，也使零篇家族无需依赖 SVG 零高度命中区。
备选：直接复用散点图不适合计数语义；引入新依赖无必要。

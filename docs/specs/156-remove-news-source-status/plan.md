# 实施计划

**Issue**：[#156](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/156)
**Spec**：[spec.md](spec.md)

## 方案与技术上下文

React 19 / TypeScript / MUI 7；只修改 NewsFeed 与中英文 news 词典。
删除面板及专用数据传递，FeedResponse 不再声明 sources，响应校验只检查实际消费的 items/total。
后台字段继续保留。复用现有 Vitest 测试覆盖失败来源不显示、缺少 sources 可读和原有阅读行为。

## 质量门与映射

| 来源 | 实现 | 验证 |
|---|---|---|
| FR-001 / SC-001 / US1 | 删除 NewsFeed 面板 | 原有 news-feed 测试调整 |
| FR-002 / SC-002 | 删除函数、回调和词典项 | 搜索引用、缺字段响应、生产构建 |
| FR-003 | 后端不变，原有组件继续使用 | 资讯/分页/历史相关测试 |

使用 mayuan，明确路径暂存；原图和原话归档。无数据迁移、接口破坏性变更或新增依赖。
实施顺序：文档和图片 → 前端删除 → 测试构建 → Overview/验收 → 独立提交。

## 文档和复杂度

spec.md、plan.md、research.md、tasks.md、quickstart.md、checklists/requirements.md、assets/。
无新数据模型或接口，所以不生成冗余 data-model 或 contracts 文件。无新增抽象。

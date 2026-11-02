# 实施计划

Issue：[#207](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/207)。日期：2026-11-02。规格：[spec.md](spec.md)。

## 技术上下文

Python/FastAPI/SQLAlchemy与Go/GORM共用MySQL；React/Vite表单保持不变。复用现有来源目录与字段结果，无迁移。pytest真实MySQL隔离事务及Go回归验证服务端；四宿主表单契约、变异和字段契约验证共享边界。同版本提交零新增模型请求，不引入逐字段全文扫描。

## 源代码边界

- backend/ingest/reviewed_sources.py：按文件、chunk、block等已有身份找到可读资料，保留引用，不比较引句与字段文字。
- backend/api/rag.py、backend/ingest/property_evidence.py：上传及现有论文持久化复用来源身份处理；未经审核的普通输入不授予通过。
- backend/ingest/scientific_evidence.py、submission_sources.py：正式来源转接不丢当前已审核依据。
- backend/services/paper_revisions.py、field_review_commit.py：原事务传递审核依据，不改角色和原子性。

## 质量门与需求映射

| 来源 | 数据事实来源与职责 | 任务及证据 |
| --- | --- | --- |
| FR-001/US1/SC-001 | 来源目录、身份解析与PaperEvidence | T001/T002/T004；失败证明及真实隔离提交 |
| FR-002/003/US2 | 当前结果、人工决定与原始引用 | T002/T003/T004；概括及两管理员事务 |
| FR-004/SC-002 | 文件身份转换和事务 | T003/T004；缺失/歧义及保存重读 |
| FR-005/SC-003/#174/#203 | 科学键和四宿主不变 | T005；字段/表单/变异和既有回归 |

## 文档结构与阶段

本目录含规格、计划、设计依据、数据模型、契约、快速验收、任务及需求清单。T001失败证明→T002共享处理→T003各入口接通→T004真实事务验证→T005回归、Overview和提交。尚未执行的检查不标通过。

## 复杂度说明

共享函数只处理来源存在与位置关系，避免多个入口分别裁决文字。拒绝删除全部来源检查，也拒绝放宽全局文本匹配来冒充统一科学审核。所有修改前核对mayuan，仅暂存本任务路径。

## 验证中补齐的直接依赖

真实隔离提交后的重读触发大型JSON排序内存错误，修正submission_metadata.py及manuscript_handoffs.py的事件排序位置，不改配置或快照。来源目录压缩引用在paper_snapshot读取前展开，避免关键词和理论子类型被误判失效。这些都是本次保存/重读链路的实际故障，验证见validation.md。

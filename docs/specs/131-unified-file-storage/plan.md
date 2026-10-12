# 实施计划：统一业务文件存储

**Issue**：[ #131](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/131)

**日期**：2026-10-12

**输入**：[Spec](spec.md)、[研究](research.md)、[数据模型](data-model.md)、[存储契约](contracts/storage.md)、[迁移契约](contracts/migration.md)。

## 技术上下文

当前为 Python 3.12/FastAPI、SQLAlchemy 2.0.52、Redis 8.1.0/RQ 2.12.0、Go 1.25/Gin/GORM、MySQL 8.4、React 19。现有代码没有 S3 适配器。目标为 Linux Docker 生产和既有 Linux/macOS 原生开发；测试使用 pytest、Go 测试、真实 MySQL/Redis/S3 与浏览器回归。

新增 boto3 和 Go S3 SDK；不升级核心依赖。持久文件访问实现见契约，首版流式上传下载，解析器仍可接收短生命周期本地路径，不要求重写所有第三方解析 API。

## 实现组织

- 新建 `backend/storage/` 与 `goserver/storage/`；配置、存储操作、临时文件管理分离，权限保留调用方。
- 接入 Python 上传/返修/人工证据、论文文件、审核快照、IR 外部产物和 Go 头像；所有业务删除走同一生命周期规则。
- 以字段清单替换直接 `Path(stored_path)`，包含 `backend/ingest/document_regions.py` 的按需渲染和旧引用下载；截图不作为唯一持久证据。
- 新建 `backend/scripts/migrate_file_storage.py`，复用现有路径安全检查思想，独立于 `make frozen/deploy` 的本地包格式。
- `backend/storage/reference_inventory.py` 是显式字段与派生路径的生产者/消费者清单；人工证据由 `row.id`/`item.id` 派生路径，候选附件、审核快照与 `clean_results` 分别按元数据、任务 ID 和论文 ID 枚举。新增持久入口必须登记，测试检测未分类文件，不能只递归搜索 `stored_path`。
- 本地既有路径由 local 实现做源根约束转换；新的 S3 路径只读对象键。`make frozen` 只支持本地存储实例，对 S3 模式明确拒绝并指向生产备份流程，不悄悄生成缺文件的包。

## 需求到设计与验证

| 来源 | 设计 | 验证 |
| --- | --- | --- |
| FR-001、FR-002 / US1 | FileRef、两个存储实现、引用清单 | SC-001、SC-004；全类别文件矩阵 |
| FR-003、FR-004、FR-010 / US1 | 既有 API 鉴权、流式写入、脱敏错误 | SC-001；越权、超限、故障与冲突 |
| FR-005、FR-006 / US1 | materialize、不可变键、业务引用清理 | SC-001、SC-004；缓存删除和共享引用 |
| FR-007、FR-008 / US2 | 清单、续跑、条件更新、回退 | SC-002、SC-003；迁移故障矩阵 |
| FR-009 / US3 | local 实现与生产无兜底 | SC-004、SC-005；原生工作流回归 |

## 阶段与依赖

先建立真实双后端测试与引用清单，再实现接口和 API 适配，最后完成历史迁移与本地兼容。#132 消费本 Feature 的配置/存储契约，#133 消费 materialize 与产物写入能力。跨 Feature 共享 `upload_tasks.py`、`upload_jobs.py`、模型和依赖文件必须串行修改。

## 质量门

| 约束 | 处理 |
| --- | --- |
| KISS/DRY | 一个业务文件接口，两种实现，不增加文件微服务和第二套权限 |
| 当前数据所有权 | MySQL 正文、IR、科学数据继续由原事务管理 |
| #35/#109/#114 | 保留清理、权限、revision 和解析语义；跨机提交机制由 #133 接续 |
| 本地兼容 | 无 Docker；生产与本地后端显式选择 |
| 实施前门槛 | 全部三个 Spec 的规划检查通过；本轮没有实施任务完成证据 |

## Documentation Impact

实现后由 Overview Skill 回写上传解析、证据、头像及数据迁移说明，更新 README 和部署文档。规划提交只包含本目录与其他两个 Feature 的文档。

# 本机原生开发库迁移验收

日期：2026-11-09。关联 [Issue #225](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/225)；代码基线为本地提交 `51443682` 的既有迁移。本轮仅执行用户指定环境的升级及必要验证，未改匹配算法、科学数据、Y-H任务或并行#226内容。

## 授权与目标

用户在Y-H人工黑盒测试中决定：“由 #225 任务完成迁移，然后继续完成这篇文章的黑盒测试。”本轮委托要求核对本机目标并完成#225迁移；Y-H任务 `d2ca41e5f16b4d65bf744f5d5325e855` 及 DOI `10.1103/PhysRevLett.119.107001` 的恢复、重新上传、送审及审批仍由原测试聊天处理。

实际目标为本机原生实时开发环境 `127.0.0.1:3307/scwiki`，MySQL 8.4.2；同步和异步连接为同一业务库，实例标识见[机器回执](assets/validation/native-migration-20261109.json)。对象存储保持 `http://127.0.0.1:39110` 的 Garage `scwiki-business` 桶，本次没有对象写入或迁移。

## 执行与数据保护

1. 核对分支为 `mayuan`、迁移文件字节与 `51443682` 一致；已有隔离演练见[首次验收](validation.md)。
2. 生成完整数据库备份 `/Users/mayuan/Codes/SC-Wiki/.local/backups/issue225-native-20261109-102551/business-before.sql`，共 1307468929 字节，文件权限 `0600`、目录权限 `0700`；SHA256为 `ae73966efe1d90f5dc417cc31372147d96cbe7653538fa85131689c57f3d9f80`。备份含私有业务数据，仅留本机，不提交仓库。备份完成后再次核对全部数据摘要；本次未在业务库演练还原。
3. 按显式目标执行 `alembic upgrade 20261106_0225`，实际仅运行 `20261102_0204 → 20261106_0225`，不stamp、不合并分支头。News分支 `20261102_0160` 保留。
4. 迁移后逐表重新读取全部旧列并比较行数与排序后内容SHA256；Go重载后再次核对，74张既有业务表数据全部不变，唯有预期的 `alembic_version` 版本记录更新。全部摘要见机器回执。
5. 本地启动校验清单同步本次迁移：Linux/Mac版本清单将0204更新为0225，结构快照仅增加下列两列、一表及LLM2约束，不重录科学字段契约。完整 `verify_schema` 已在真实业务库通过。
6. Go进程持有旧的 `SCWIKI_SCHEMA_HEADS`，仅重启本机 `goserver` 加载新值；Python、上传Worker及其他服务未重启，未触发Y-H恢复。Python和Go的 `/readyz` 均返回200且依赖全真。

## 实际结构与版本

| 对象 | 迁移后状态 |
| --- | --- |
| `alembic_version` | `20261102_0160`、`20261106_0225` |
| `citation_match_cache` | 已创建：`cache_key` 主键、`payload` JSON、`created_at`；0行 |
| `paper_reference_extractions.matching_snapshot` | JSON、可空；4条已有提取记录均为NULL |
| `paper_references.match_evidence` | JSON、可空；211条已有引用均为NULL |
| `ck_paper_references_match_method` | 保留doi/title_year/manual并新增llm2 |
| 其他旧表结构 | 与迁移前一致 |

正式SQLAlchemy ORM已成功查询新增缓存、4条提取及211条引用，未出现原缺列1054。没有调用模型、生成匹配结果、修改历史边或执行历史回填；缓存保持为空是本次迁移的预期状态。

## 验证与交接

[部署与运行时结构回归](assets/validation/native-schema-tests-20261109.log)：48通过、11条件不适用而跳过，不把跳过计为通过；完整业务结构核验及Python/Go就绪检查通过。本次只改变数据库结构及对应本地校验清单，不改科学表单组件，未重复整篇科学解析或表单交互验收。

Y-H的Redis state/draft键在核对开始时均已不存在，迁移前后状态相同；未创建或恢复这些键。SQL工作稿及全部既有业务表摘要保持。本报告只证明迁移阻塞解除，不认定Y-H解析、审核或入库已完成。原测试聊天可据此继续其授权的恢复流程。

本轮未推送Git、未构建发布镜像、未部署阿里云。Issue保持OPEN，原远程Spec未发布的检查仍独立保留。

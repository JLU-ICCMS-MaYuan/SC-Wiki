# 验收与运行

## 前置条件

使用 Go、Node 与现有前端依赖；持久化验收使用隔离 MySQL 8 和 Redis。既有数据库应用迁移须单独确认。新 revision 为 20260917_0107，依赖当前工作区 20260916_0106；并行分支 20260914_0052 保留。不得把未提交前置迁移算作本 Feature 提交。

## 验证命令

```bash
cd goserver
go test ./...
cd ..
frontend/node_modules/.bin/vitest run --config vitest.config.ts tests/07_researcher_community_forum
npm --prefix frontend run build
git diff --check
```

隔离数据库集成测试的专用连接只通过环境传入，不在验收记录中保存密码。

使用安装了项目 SQLAlchemy、PyMySQL、Alembic 依赖的 Python，并确保 Docker 可用：

```bash
python tests/07_researcher_community_forum/verify-community.py --browser
```

脚本只启动并清理自己的随机命名 MySQL 8.4 与 Redis 7 容器，数据库固定为 `scwiki_community_test`。既有身份和论文边界使用模型建立测试夹具；六张社区表实际执行新增迁移的升级、降级、再升级。它不验证整条历史迁移链，也不连接现有业务库。`SCWIKI_GO_BIN`、`PLAYWRIGHT_MODULE`、`CHROMIUM_PATH` 可指定本机 Go 和 Playwright/Chromium 路径；不传 `--browser` 时只运行迁移与 Go 数据库集成验收。

## 浏览器验收路径

1. 展开社区，分别打开排行榜、Tc~X 演变、讨论，验证原榜单与图表。
2. 账号甲提问，乙回答，甲点赞、评论，乙回复；检查通知数、列表、已读与定位。
3. 元素搜索 Hg，打开体系页，发布评论；由两个不同论文入口确认体系共享、论文隔离。
4. 两个窗口进入同一体系或论文，发送弹幕，验证数秒同步、历史、关闭、后台暂停及断网恢复。
5. 举报内容，管理员填写原因隐藏与恢复；检查作者无法绕过隐藏、通知不泄漏不可见内容。
6. 检查桌面及 390px 窄屏、中文与英文、键盘焦点及减少动画设置。

## 执行记录

2026-09-17 在当前工作区完成以下验证：

| 验证层 | 结果与覆盖 |
| --- | --- |
| Go 全量 | `go test ./...` 通过；社区追加断言也单独重跑通过 |
| Go 竞态检测 | `go test -race ./handlers -run '^TestCommunity' -count=1` 通过；未配置专用 DSN 时 MySQL 测试明确跳过，数据库结果见下一行 |
| 真实 MySQL 8.4 / Redis 7 | 迁移升级→降级→升级通过；3 项集成测试通过，覆盖持久化、并发幂等点赞、体系归一化、论文版本及可见性、删除级联、失效通知、隐藏根评论与回复竞争、隐藏答案与评论竞争 |
| 前端交互与回归 | 社区目录及侧栏共 4 个测试文件、38 项通过，覆盖安全 Markdown、草稿保留、评论回复、权限失败、弹幕排队、隐藏及网络恢复去重，原贡献展示与 Tc 图表交互继续通过 |
| 前端生产构建 | `npm --prefix frontend run build` 通过；仍有既有 3Dmol 的 eval 提示和大文件体积提示 |
| 浏览器 | 10 组通过：双账号问答/点赞/评论回复、点赞保留双草稿、通知定位、Hg 检索入口及共享讨论、双浏览器弹幕同步/开关/历史、举报隐藏、三个论文入口一致、榜单与图表及 390px 导航、断网恢复、中英文/键盘焦点/减少动画 |

浏览器的社区接口和论文详情连接真实 Go、MySQL、Redis。图表抽屉验收仅为原科学图表数据接口提供一个已知散点夹具，用于稳定点击；它证明抽屉接入共用真实评论，不代表完整科学数据统计链路的端到端验收。管理员恢复及审计记录、点赞取消、越权与跨目标、封禁和注销等边界由 Go 行为测试覆盖。

本机日志：`/tmp/scwiki-community-go-all.log`、`/tmp/scwiki-community-go.log`、`/tmp/scwiki-community-race.log`、`/tmp/scwiki-community-vitest.log`、`/tmp/scwiki-community-build.log`、`/tmp/scwiki-community-integration.log`。浏览器截图与结果位于 `/tmp/scwiki-community-acceptance-ad4y5g8g/`；临时账号令牌及数据库凭据已由脚本清理。

独立审查发现的长线程定位、回复归组、并发隐藏、弹幕溢出与重播、点赞清空草稿已修复，并以相应行为测试验证。需求 FR-001–FR-012 与 SC-001–SC-005 的映射见 [计划](plan.md) 和 [任务](tasks.md)。评论、弹幕与三个论文入口复用共享组件及目标权限规则，减少重复实现；本期不引入编辑器或长连接依赖。

## 当前交付边界

- 现有数据库未应用 `20260917_0107`，现有服务未由本任务重启或部署。
- 新迁移依赖当前工作区前置迁移 `20260916_0106`，该前置迁移及其他任务原有修改不纳入本次提交。部署时必须先确认前置链完整，并明确执行目标 revision，保留并行分支。
- 应用现有数据库迁移属于仓库要求单独确认的结构变更。确认后先核对目标库版本，再执行 `alembic upgrade 20260917_0107`，配套更新 Go 与前端，并在目标环境复验问答、论文评论与弹幕。
- 未推送。本地实现、隔离验收和目标环境启用分别报告；Issue #106 保持开放以跟踪后续启用与目标环境验收。

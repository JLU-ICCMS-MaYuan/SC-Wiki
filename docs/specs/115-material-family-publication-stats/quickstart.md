# 验证路径

## 前置条件

Go 1.25、已安装的 frontend npm 依赖、项目 Python 环境中的 MySQL 与 pymysql。集成脚本自动创建临时数据目录，通过 Unix socket 启动隔离 MySQL，并使用内存 Redis；不读取业务配置或连接业务库。具备 C 编译器时也可直接运行 Go 测试的 SQLite 路径。

## 自动检查

从仓库根执行：

```bash
conda run -n sc-wiki python "scripts/run_issue115_integration.py"
(cd "frontend" && npm run test:upload-ui -- tests/07_researcher_community_forum/publication-stats.test.tsx tests/07_researcher_community_forum/community-charts.test.tsx)
(cd "frontend" && npm run build)
```

## 隔离页面夹具

先完成前端构建，再执行：

```bash
conda run --no-capture-output -n sc-wiki python "scripts/run_issue115_integration.py" --browser
```

打开 `http://127.0.0.1:19115/share/rankings`。家族统计使用真实生产聚合接口、隔离 MySQL 和构建后的 SPA；贡献榜和分类目录接口仅返回夹具数据。无需登录，避免影响业务服务。创建脚本输出的停止文件可结束夹具；否则 15 分钟后退出并清理临时数据库。运行时需保证 19115 端口空闲。

## 页面验收

1. 以访客进入 `/share/rankings`，检查现有贡献榜下方的家族柱图；目录家族含零篇项，无分类论文计入未分类。
2. 点击有跨年数据的家族，检查高亮、年份顺序、缺年零值、未知年份说明及数量守恒。
3. 点击另一家族，再次点击当前家族及收起按钮，核对切换和收起；用 Tab 与 Enter 复验。
4. 检查零篇家族、全部年份未知家族、中文及英文、375px 窄屏；页面不横向溢出。
5. 点击“刷新榜单”及统计区域刷新，确认新快照完整更新；模拟网络失败后重试，旧数据显示与错误提示一致。
6. 登录后贡献榜个人排名继续显示；新统计与访客一致。

## 验证记录

2026-09-24：

- 前端新增交互与匿名/登录集成测试 9 项通过；既有社区图表回归 20 项通过。
- 隔离 MySQL 8.4.2 下 4 项新统计测试和 4 项贡献榜回归测试通过；浏览器夹具单独运行通过。
- 验证了真实 SQL 去重、当前版本过滤、目录零篇、未知年份、补零守恒、缓存 TTL、强制刷新、数据库失败及 Redis 不可用的降级。失败用例故意移除隔离库表，日志中的表缺失是预期故障注入。
- 浏览器使用实际 MySQL 统计接口与完整 SPA，验证初始收起、点击展开、家族切换、零篇提示、收起及统一刷新；375px 宽度下页面宽度 360px，图表内部滚动，控制台无错误。
- `npm run build` 与 Go 服务构建通过；前端仅出现既有大包和 3Dmol eval 提示。
- 本机缺少 C 编译器，SQLite 测试驱动无法运行；改用上述实际 MySQL 验证，未安装全局编译器。
- 未推送或部署，不将隔离验收结果表述为业务运行环境已生效。

# 验收记录

日期：2026-09-09。对应 [Issue #99](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/99)。

## 需求与证据

| 来源 | 实际验证 | 结果 |
| --- | --- | --- |
| FR-001/002、SC-001 | 当前开发服务，Chromium，1440px 与 390px 两个视口，上传与管理员真实页面测量六字段位置和宽度 | 同一行，顺序正确，4:1:1:1:1:4；窄屏书目行可横向滚动 |
| FR-003/004、SC-002 | `backend/tests/test_issue99_metadata.py`，当前 scwiki MySQL 与 Redis，真实草稿 PUT/GET 和提交函数 | 6 项通过；文本期号及数字转文本正确，提交后 S1 与历史页码范围保留 |
| FR-003/004/005、SC-002 | `TestCurrentMySQLPaperMetadata`，当前 MySQL，Gin 真实鉴权、管理员 PUT、详情 GET、修改历史事务 | 通过；旧值 null、S1、3-4、空字符串及 null 清空正确，页码范围不变，非法类型/超长值返回 400 |
| FR-004、US1 | Chromium 访问运行中的 Vite→Go→Python 服务，独立验证草稿输入 S1、点击立即保存并刷新 | 真实 HTTP 保存成功，刷新后期号仍为 S1 |
| FR-005、SC-003 | 原上传布局、提交反馈、管理员结构上传三份前端回归 | 32 项通过，包含 DOI 与其他错误定位、保存提交反馈 |
| FR-001/004、US1/US2 | 上述布局和管理员测试新增书目保存回归，按“书目”筛选执行 | 新增 2 项通过 |
| SC-003 | `frontend/` 执行 `npm run build` | TypeScript 与 Vite 构建通过；只有已有 3dmol eval 与产物体积警告 |

## 当前数据库与运行版本

`alembic upgrade head` 已在当前 scwiki 执行，版本从 `issue90_data_integrity_repair_v1` 升到
`20260909_0099`。仅新增可空列，无历史回填或科学数据修改。

Python 与 Go MySQL 验证的论文和历史写入均在外层事务回滚，随后确认测试论文不存在。
Redis 使用独立验证任务键，测试后删除；浏览器没有改写既有论文。未创建 SQLite 或临时测试数据库。

浏览器访问运行中的开发服务，确认热重载已加载本次源码。验证时运行制品来自本次工作树，
最终提交后内容与该工作树一致；未推送远端，不代表其他部署环境已更新。

## 复现命令

加载项目 `.env` 后，设置 `SCWIKI_CURRENT_MYSQL=1`，使用 sc-wiki Python 环境运行：

```bash
PYTHONPATH=. python -m pytest "backend/tests/test_issue99_metadata.py" -q
```

Go 测试同时需要 `SCWIKI_TEST_MYSQL_DSN`（由当前 `DATABASE_URL` 转成 Go MySQL DSN，
不要输出凭据），在 `goserver/` 运行：

```bash
go test ./handlers -run '^TestCurrentMySQLPaperMetadata$' -count=1 -v
```

未设置显式选择变量时两项真实数据库测试自动跳过。浏览器截图与驱动是本地验收产物，
不作为业务依赖。完整链路不依赖 Mock；前端 Mock 测试仅用于字段事件和回归定位。

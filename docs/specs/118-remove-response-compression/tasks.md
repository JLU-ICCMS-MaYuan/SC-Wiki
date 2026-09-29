# 实施任务：移除应用层双重响应压缩

**输入**：[Spec](spec.md)、[Plan](plan.md)、[Research](research.md)、[Quickstart](quickstart.md)

Issue 状态由 [#118](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/118) 管理。

## 阶段 1：US1 解析详情正常显示（P1）

**独立验收**：三入口均返回未编码 JSON，解析详情接口可解析。

- [x] T001 [P] [US1] 删除 `backend/main.py` 中 `GZipMiddleware` 的导入与注册。（FR-001）
- [x] T002 [P] [US1] 删除 `goserver/main.go` 中 `gzipMiddleware`、`gzipWriter`、注册调用及不再使用的导入。（FR-002）
- [x] T003 [US1] 删除 `goserver/main_test.go` 的 `TestGzipMiddlewareDropsLateContentLength` 及不再使用的导入；删除 `goserver/handlers/paper_evidence_mysql_test.go` 中无作用的 `Accept-Encoding` 清除。（FR-004）
- [x] T004 [US1] 重启 python、goserver，按 [Quickstart](quickstart.md) 实测三入口与解析详情接口。（SC-001、SC-002）

## 阶段 2：US2 清理绕过配置与说明（P2）

**独立验收**：源码、配置、测试与当前文档中不再存在响应压缩及其绕过。

- [x] T005 [P] [US2] 删除 `docker/nginx.conf` 两处 `proxy_set_header Accept-Encoding ""` 及压缩相关注释。（FR-003）
- [x] T006 [P] [US2] 删除 `docs/overview/02_Decentralized_Maintenance_and_Verification/deployment-and-runtime.md` 与 `docs/local-dev.md` 中 `Accept-Encoding` 差异项及 GZipMiddleware 说明。（FR-005）
- [x] T007 [US2] 检索仓库确认无残留；执行 Go 全包测试与相关 Python 测试。（SC-003）

## 执行记录（2026-09-29）

- T004：三入口 curl 与解析详情序列化通过；用户登录后在浏览器打开 H3S 解析详情，pattern 报错消失、处理步骤正常显示。同页草稿接口的 500 为 Mac 环境缺少 greenlet，另行跟踪，不属于本 Issue。
- T007：Go 全包测试通过；定向 pytest 14 项通过。`tests/test_structures_api.py` 4 项失败在基线 `eb17255` 上同样出现（SQLite `chemical_systems.paper_id` 非空约束），与本次无关。

## 依赖与执行顺序

T001、T002 可并行 → T003 → T004；T005、T006 可并行 → T007。阶段 2 不依赖阶段 1 的运行验证。

## 需求覆盖

| 来源 | 任务 |
|------|------|
| FR-001 / US1 | T001、T004 |
| FR-002 / US1 | T002、T004 |
| FR-003 / US2 | T005、T007 |
| FR-004 | T003、T007 |
| FR-005 / US2 | T006、T007 |
| SC-001、SC-002 | T004 |
| SC-003 | T007 |

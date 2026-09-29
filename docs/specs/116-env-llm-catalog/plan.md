# 实施计划：编号 LLM 配置与服务端模型目录

**Issue**：[#116](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/116)；**日期**：2026-09-29；[Spec](spec.md)、[决策](research.md)。

## 技术上下文

Python 3.12、FastAPI、SQLAlchemy、Redis/RQ、React/TypeScript、Docker Compose；不新增数据库表或第三方运行依赖。使用 pytest、Vitest 和前端生产构建，集成验证复用独立 Linux 容器。

## 组件与职责

- `backend/rag/llm_catalog.py`：纯解析、缓存环境读取、安全目录元数据。
- `backend/rag/llm_context.py`：来源选择、默认兼容、请求登录边界与展示信息；统一客户端保持复用。
- `backend/api/rag.py`：提供受认证保护的目录接口，原默认配置管理接口保留。
- `backend/ingest/upload_tasks.py`、`upload_jobs.py`：保存来源快照，防止编号任务丢失快照后换模型。
- `frontend/src/lib/llmProvider.ts`：个人配置和服务端 ID 的互斥本地存储/请求头。
- `frontend/src/components/LlmProviderSwitcher.tsx`：登录后加载目录，选择服务端模型时隐藏密钥表单，失效项提示重新选择。
- `docker/compose.yaml`、`scripts/export-llm-env.py`、配置示例和部署说明：让任意编号进入 API/Worker。

## 质量门与映射

| 需求 | 决策/组件 | 任务 | 验证 |
|---|---|---|---|
| FR-001/002/007，US1 | D-001，目录解析 | T001/T002 | 纯解析边界、默认兼容 |
| FR-003/004/005/006，US2 | D-002/003/004，请求与接口 | T003/T004 | 真认证 ASGI 拒绝与脱敏、双上游 |
| FR-008/009，US2 | D-005/006，任务快照 | T005 | Redis、Worker、失效不回退 |
| FR-003/005，US2/US3 | 选择器与存储 | T006 | Vitest 操作、请求头、生产构建 |
| FR-010/011，US3 | D-007/008，部署与文档 | T007/T008 | Compose 渲染、部署与 #73 回归 |

文档门：全部产物与上述映射存在，无新增表，权限已获确认，原业务来源不改变；先完成需求检查再写实现。源码修改和提交均核对 `mayuan`，只提交本项文件。

## 执行顺序

解析与失败测试 → 请求/目录接口 → Worker → 前端 → 配置传递 → 定向测试和隔离集成 → 文档与提交。共享文件串行修改，不使用多 Agent。


## 收尾映射

FR-002/009、SC-004 → T009/T010：修正连接测试的推理预算与错误类别，复用既有统一客户端，不新增供应商协议。FR-003/004/010、SC-002/004 → T011：当前 Mac 代理、身份与实际编号配置验证；健康检查与真实供应商返回分别记录。文档与协作状态 → T012：用户已授权 README 收尾，既有 Spec/Overview 内容据实更新。

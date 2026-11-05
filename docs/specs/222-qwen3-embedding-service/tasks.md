# 实施任务：独立 Qwen3-Embedding-4B 服务

输入：[Spec](spec.md)、[Plan](plan.md)、[Research](research.md)、[数据所有权](data-model.md)、[接口](contracts/http.md)。

## 阶段 1：文档与制品

- [x] T001 建立 Issue #222 与本目录设计，核实服务器、模型、现行索引边界及原始部署授权。
- [x] T002 在 scripts/embedding/model-manifest.json 固定 HF revision 及文件哈希。

## 阶段 2：US1 独立生成向量（P1）

- [x] T003 在 scripts/embedding/ 建立固定版本启动、下载、systemd 模板与真实接口冒烟脚本，检查 CLI 及结构；实际运行见 evidence/runtime-facts.json。
- [x] T004 在 /home/singeuser/qwen3-embedding 安装隔离环境、验证权重、生成私有密钥并启用本次服务；模型校验与 pip check 见 evidence/finalize.log。
- [x] T005 执行真实 GPU 单条/批量、2560/1536/32 维、鉴权、错误输入、相似度、重启及异常自动恢复；见 evidence/smoke-*.json、recovery.json。
- [x] T006 验证受限反向隧道后的外部 HTTPS 与退出全部交互 SSH 后的应用调用，见 evidence/connection-https-smoke.json、connection-after-ssh-logout.json。

## 阶段 3：交付

- [x] T007 写 quickstart.md 与 validation.md，按真实证据更新 Overview 和 Issue，明确机器内通过及外部未通过的边界；Git 提交另按仓库规则仅纳入本次路径。

## 依赖与覆盖

T001 → T002 → T003 → T004 → T005 → T006 → T007。同一文件串行更新。

| 需求 | 任务 | 验收 |
| --- | --- | --- |
| FR-001 | T002–T005 | 权重、依赖、源码及 GPU 身份 |
| FR-002、FR-003 | T003、T005 | 批量对应、维度、范数、真实相似度 |
| FR-004 | T004–T006 | 密钥拒绝与受控跨机通道 |
| FR-005 | T004–T006 | systemd、自启和退出 SSH 后状态 |
| FR-006 | T006–T007 | 外部调用或明确阻塞、操作与证据文档 |

复选框只记录技术执行；未完成行动状态以 Issue 为准，不因文档存在就勾选推理验收。

## 澄清补充：外部 HTTPS 入口

- [x] T008 [US2] 用户最新接入指令后，单条标准 SSH 命令实际成功，部署专用公钥账号与 Caddy 持久片段；外部 HTTPS、受限路径、隧道重启恢复通过。没有绕过审核，也没有切换阿里云站点自身模型。

FR-007 / SC-006 由 T008 覆盖；依赖 T004–T005、可用网络通道及相应授权。本项以 Issue 记录外部依赖，不另建本地协作状态。

T006/T008 的最初未完成状态已被最新授权及真实接入验证替代，保留初始验收文件供历史对照，不再以当时的等待状态描述当前链路。

## 本次新增授权：接入本地 SC-Wiki

用户明确要求开始接入，既有待授权说明保留为历史；本次不再以原先仅检查的授权范围阻止必要接入工作。

- [x] T009 在 backend/rag/config.py、backend/ingest/embedder.py、backend/rag/vectordb.py、backend/rag/search/vector_search.py 实现查询指令与独立集合；RAG 单元目录 34 项通过，见 evidence/connection-unit-tests.txt。
- [x] T010 新增 scripts/embedding/rebuild_collection.py，私有备份并实际重建 1072 条，核验源/目标 ID、payload 及源摘要，见 evidence/connection-rebuild-receipt.json、connection-data-preservation.json。
- [x] T011 专用隧道、HTTPS、本地六项配置及原运行的 Python/Worker 切换完成；实际向量写入、前端入口查询及断开交互 SSH 后查询通过，见 evidence/connection-*.json。

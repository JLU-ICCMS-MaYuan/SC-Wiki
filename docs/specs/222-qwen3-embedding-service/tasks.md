# 实施任务：独立 Qwen3-Embedding-4B 服务

输入：[Spec](spec.md)、[Plan](plan.md)、[Research](research.md)、[数据所有权](data-model.md)、[接口](contracts/http.md)。

## 阶段 1：文档与制品

- [x] T001 建立 Issue #222 与本目录设计，核实服务器、模型、现行索引边界及原始部署授权。
- [ ] T002 在 scripts/embedding/model-manifest.json 固定 HF revision 及文件哈希。

## 阶段 2：US1 独立生成向量（P1）

- [ ] T003 在 scripts/embedding/ 建立固定版本启动、下载、systemd 模板与真实接口冒烟脚本，检查 CLI 及结构。
- [ ] T004 在 /home/singeuser/qwen3-embedding 安装隔离环境、验证权重、生成私有密钥并启用本次服务。
- [ ] T005 执行真实 GPU 单条/批量、2560/1536 维、鉴权、错误输入、相似度和重启恢复验收。
- [ ] T006 验证 SSH 转发后的外部客户端调用及 SSH 退出后常驻；不支持时在 Issue 记录外部依赖。

## 阶段 3：交付

- [ ] T007 写 quickstart.md 与 validation.md，按真实结果更新 Overview 和 Issue；验证变更后仅提交本次路径。

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

# 实施任务：独立 Qwen3-Embedding-4B 服务

输入：[Spec](spec.md)、[Plan](plan.md)、[Research](research.md)、[数据所有权](data-model.md)、[接口](contracts/http.md)。

## 阶段 1：文档与制品

- [x] T001 建立 Issue #222 与本目录设计，核实服务器、模型、现行索引边界及原始部署授权。
- [x] T002 在 scripts/embedding/model-manifest.json 固定 HF revision 及文件哈希。

## 阶段 2：US1 独立生成向量（P1）

- [x] T003 在 scripts/embedding/ 建立固定版本启动、下载、systemd 模板与真实接口冒烟脚本，检查 CLI 及结构；实际运行见 evidence/runtime-facts.json。
- [x] T004 在 /home/singeuser/qwen3-embedding 安装隔离环境、验证权重、生成私有密钥并启用本次服务；模型校验与 pip check 见 evidence/finalize.log。
- [x] T005 执行真实 GPU 单条/批量、2560/1536/32 维、鉴权、错误输入、相似度、重启及异常自动恢复；见 evidence/smoke-*.json、recovery.json。
- [ ] T006 验证 SSH 转发后的外部客户端调用及 SSH 退出后常驻；不支持时在 Issue 记录外部依赖。

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

- [ ] T008 [US2] 取得平台映射信息，或在平台审核放行且用户授权后配置阿里云受限反向隧道及 Caddy HTTPS 入口，并验证本地客户端。记录未来阿里云消费方式，不提前切换生产模型。

FR-007 / SC-006 由 T008 覆盖；依赖 T004–T005、可用网络通道及相应授权。本项以 Issue 记录外部依赖，不另建本地协作状态。

T006 的 SSH 退出后常驻部分已通过 evidence/logout-verification.json；跨机 HTTP 入口尚未交付，所以整项保持未勾选。T008 的阿里云草案只通过配置校验，尚未获部署授权，不能以草案代替实际连接。

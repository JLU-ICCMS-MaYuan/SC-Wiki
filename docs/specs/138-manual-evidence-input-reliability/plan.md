# 实施计划：人工证据输入与编辑可靠性

**Issue**：[#138](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/138)；**日期**：2026-10-15；**Spec**：[spec.md](spec.md)。

## 摘要

先稳定人工修改草稿与当前表单/服务端版本的衔接，再添加拖拽与剪贴板图片入口。侧栏负责交互，编辑工作流管理会话草稿与请求顺序，服务器继续裁定字段变化、版本、权限和文件有效性。复用 #109 的保存主路径，不新增数据库迁移。

本轮产物是实施设计与任务拆解；尚未写业务代码或执行功能验收。

## 技术上下文

- **语言与版本**：TypeScript ~5.6.0，React ^19.2.6，MUI ^7.3.5；Vite ^5.4.0。版本范围来自 `frontend/package.json`，不等同于部署运行版本。
- **主要依赖**：现有 React/MUI、Fetch/FormData、浏览器 DragEvent/ClipboardEvent；不计划新增依赖。
- **数据存储**：已保存说明使用既有 MySQL 人工证据表与文件存储抽象；未保存草稿由编辑工作流在当前会话内管理，不将 File 序列化进 localStorage。
- **测试体系**：Vitest ^2.1.9、Testing Library、jsdom，配置 `vitest.config.ts`；已有 Python 人工证据接口测试及真实浏览器/隔离存储验收。
- **目标平台**：桌面 Chrome/Safari 等支持标准拖拽和用户粘贴事件的浏览器；移动窄屏保留点击选择与正常编辑。
- **性能目标**：FR-005/SC-002 的入口呈现不等待 5000 毫秒自动保存；异步准备显示状态，无需刷新。没有未经确认的毫秒级服务器 SLA。
- **约束**：每文件 10 MiB、每字段 5 项；既有权限/版本/历史与原文隔离不变；不自动推送、部署或操作业务库。
- **规模范围**：一个共用侧栏及上传、返修、管理员、超级管理员四种入口；覆盖多字段/多任务隔离。

## 质量门

| 约束来源 | 强制要求 | 设计如何满足 | 状态 |
|---|---|---|---|
| AGENTS.md | mayuan；只提交本任务文件 | 新文档独立目录；提交前核对分支与暂存范围 | 本轮执行时核对 |
| Spec 原文与确认 | 已确认范围，无隐含新增功能 | spec.md 保留完整原文和“开始”；FR-001—010 未扩大 | 需求门通过 |
| Overview / #109 | 保持审计、来源及保存主路径 | D2/D5；共同保存顺序，不创建第二套流程 | 设计满足，实施待验证 |
| FR-006/008 | 新输入不被旧响应覆盖 | D1/D3；字段身份、值身份与修订控制 | 实施待验证 |
| FR-001—004 | 一致入口与文件约束 | D4；统一附件候选，服务端最终校验 | 实施待验证 |
| SC-005 | 真实浏览器与运行来源证据 | quickstart 的导航、交互及四入口矩阵 | 待执行 |
| Skill 远程链接门 | 远端文件实际可读才通过 | Issue 只登记相对路径与待验证，不自行推送 | 未满足，不作为关闭依据 |

需求基线已经确认；本地文档审查与远程发布/功能验收分开记录。远程链接未验证时不能宣称完整文档门或 Issue 关闭门全部通过。

## Feature 文档结构

```text
docs/specs/138-manual-evidence-input-reliability/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── contracts/manual-evidence.md
├── quickstart.md
├── tasks.md
└── checklists/requirements.md
```

## 源代码结构

```text
frontend/src/components/ManualEvidenceSection.tsx
frontend/src/components/EvidenceWorkflow.tsx
frontend/src/components/UploadTaskEditor.tsx
frontend/src/pages/AdminPaperEditPage.tsx
frontend/src/lib/evidenceFields.ts
frontend/src/lib/evidenceDraftQueue.ts
frontend/src/lib/manualEvidenceDrafts.ts                 # 拟新增，会话草稿与修订控制
frontend/src/i18n/{zh,en}/evidence.ts
backend/api/evidence.py                                 # 沿用契约，核查与回归
backend/ingest/manual_evidence.py                        # 沿用类型/权限/大小/数量约束
tests/01_decentralized_uploading/manual-evidence-section.test.tsx
tests/01_decentralized_uploading/manual-evidence-drafts.test.tsx   # 拟新增
tests/01_decentralized_uploading/manual-evidence-editor.test.tsx   # 拟新增
tests/01_decentralized_uploading/test_issue109_manual_api.py
```

**结构选择**：在现有 hook 作用域集中草稿和保存职责；侧栏只通过管理器操作对应字段。既有文件输入和新 drop/paste 共用人工附件处理路径，不复用主文上传接口或其 50 MiB 限制。共享文件的修改按顺序执行，保护其他任务当前未提交改动。

## 保存与读取流程

1. 主表单编辑更新当前值及本地修订；打开侧栏立即显示人工编辑/待同步入口，不调用模型、不隐式写服务端。
2. 首次加载说明时记录目标、稳定字段、值和输入修订。初始化只填充尚无本地编辑的对应草稿。
3. 显式保存/上传前，通过已有保存入口等待当前主表单保存；失败停在当前阶段，保留所有本地输入。
4. 重取当前 preflight 和人工记录，核对目标及字段值。整份版本变化但本字段未变时允许重取后继续；字段值变化时阻止旧说明/文件自动写入新值。
5. 写说明，随后按既有接口上传待处理文件。逐项确认结果；成功只确认请求所携带的本地修订，失败保留待处理项并显示实际阶段。
6. 关闭/重开侧栏保留会话草稿；确认保存成功且无未上传项时沿用 #109 的成功反馈、关闭与焦点恢复规则。刷新后仅从服务端恢复已经保存的内容及附件；未保存/未上传项须明确处理，不能被称为已持久化。

## 需求到设计的映射

| 来源 | 设计组件/接口 | 任务 | 验证方式 |
|---|---|---|---|
| US1 / FR-006 / SC-003 | D1/D3、manualEvidenceDrafts、工作流与侧栏 | T003—T005 | 多字段、侧栏重开、迟到响应 |
| US1 / FR-007 / SC-005 | D3/D4、事件默认行为与导航调查 | T001、T004、T007、T011 | 实际导航记录与交互复现 |
| US1 / FR-008—009 / SC-004 | D2/D3/D5、共同保存顺序和服务端恢复 | T004—T005、T009—T010 | 409、部分成功、刷新重读 |
| US2 / FR-005 / SC-002 | D2、getCurrentValue 与主表单保存后同步 | T006—T008 | 立即打开/保存后打开 |
| US3 / FR-001—004 / SC-001 | D4、统一文件候选入口和局部事件处理 | T009—T010 | 点击/拖拽/图片粘贴矩阵 |
| 全故事 / FR-010 / SC-005 | 共用组件、现有鉴权/历史/提交门 | T008、T010—T012 | 四入口、真实存储、浏览器回归 |

## 阶段与依赖

1. T001—T002：复核运行来源、#109 进展与保存契约；调查整页刷新。
2. T003—T005：US1，会话草稿与保护性写入，完成输入保留的 MVP。
3. T006—T008：US2，即时入口与主表单/版本同步。
4. T009—T010：US3，在相同可靠路径接入拖拽和图片粘贴。
5. T011—T012：真实浏览器/存储、跨入口回归及文档收尾。

## 复杂度说明

| 必要复杂度 | 为什么需要 | 未采用的简化方式及原因 |
|---|---|---|
| 字段级草稿及请求修订 | 多字段与延迟响应不能互相覆盖 | 仅在组件内 useState 或响应全量覆盖无法保留编辑 |
| 分阶段保存与部分成功 | 主值、说明、文件是现有独立请求 | 单一“保存成功”会掩盖上传失败并导致重试丢失 |
| 即时 UI 与服务端裁定分离 | 未保存值需立即可补证，最终审计仍须可信 | 等五秒或随意接受客户端 changed 均不满足要求 |

不引入通用状态框架、额外数据库表或全站上传重构，遵循 KISS、DRY、YAGNI；编辑流程、展示和服务端校验各自单一职责。

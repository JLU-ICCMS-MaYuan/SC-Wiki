# 实施计划：图谱科学标题表单入口

**Issue**：[#173](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/173)

**日期**：2026-10-28；**规格**：[spec.md](spec.md)

## 摘要与技术上下文

React 19、TypeScript 5.6、MUI 7 的现有上传表单增加一个 `ReviewPaperTextField`，补齐 `PaperDraftFields` 的可空文本类型与中英文界面文案。草稿仍使用现有 Redis/MySQL 保存路径，无数据库迁移、API 新增或生成逻辑变更。

验证使用现有 Vitest/jsdom、真实浏览器与已有后端测试。规模限定一个字段、上传及复用上传编辑器的返修入口；目标为桌面与窄屏网页，不新增网络请求或性能指标。

## 质量门

| 来源 | 要求与处理 | 状态 |
| --- | --- | --- |
| Spec | 用户已对完整 Spec 授权实现与验证 | 通过 |
| AGENTS.md | mayuan 分支、保留已有改动、任务独立提交、不推送 | 实施中持续核对 |
| 数据约定 | 当前草稿为唯一值来源，可空、独立于原标题 | 通过设计检查 |
| 技能链接门 | 本地文件指向 #173；远程文件未推送 | 远程链接待验证，保留 Issue 开放 |

## 文档与源代码结构

本目录包含 spec、plan、research、data-model、quickstart、tasks、contracts/ui.md、checklists/requirements.md 和验收后的 validation.md。图片使用 assets/IMG-001.png。

- `frontend/src/components/UploadTaskEditor.tsx`：原标题之后增加同样跨栏的输入控件。
- `frontend/src/lib/paperProcessing.ts`：`knowledge_graph_title?: string | null`。
- `frontend/src/i18n/{zh,en}/upload.ts`：名称、用途及键名。
- `tests/01_decentralized_uploading/graph-title-form.test.tsx`：完整宿主回归。
- `tests/01_decentralized_uploading/graph-title-browser.mjs`：正式页面浏览器验收，API 隔离。
- `tests/01_decentralized_uploading/test_graph_title_form_mysql.py`：生产保存函数与 MySQL／Redis 重读、版本冲突和旧核对失效验证，临时数据清理回滚。

## 需求到设计与任务的映射

| 来源 | 设计决策与事实来源 | 任务 | 验证 |
| --- | --- | --- | --- |
| FR-001、002、007 / SC-001 | 控件直接读取 draft.paper，空值显示空文本，不填充默认标题 | T002、T003 | 有值、空值、缺失及窄屏 |
| FR-003、006 / SC-002、004 | 复用 setPaperField、createFieldDraftSaver、保存错误与 revision.conflict | T002–T004 | PATCH 精确字段、重载、失败、只读与冲突 |
| FR-004、005 / SC-003 | data-issue-field 精确绑定，复用 ReviewPaperTextField 与 EvidenceWorkflow | T002–T004 | 真组件定位、侧栏当前值与编辑失效 |

## 阶段、依赖与复杂度

先写回确认并完成文档（T001），再编写回归（T002），补齐控件及类型文案（T003），运行验证（T004），回写已落地文档并提交（T005）。同一文件串行修改。

仅复用既有组件与保存器，不新增抽象、后端接口或兼容分支。旧草稿缺失字段由现有空值展示处理；无需迁移。回滚本次前端改动即可恢复旧展示，不删除保存的数据。

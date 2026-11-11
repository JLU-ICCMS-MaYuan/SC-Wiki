# 实施计划：支持解析人工问题追加排队、字段暂挂与回答后局部恢复

**Issue**：[239](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/239)；**日期**：2026-11-11；**规格**：[spec.md](spec.md)。已按spec.md末尾本轮实施授权接线；具体已验证事实与未完成业务范围见validation.md。

## 摘要

问题队列和局部补做：human_questions.py负责问题生命周期和指令边界；material_batches.py负责局部进度；现有保存与证据仍为唯一写入链。

## 技术上下文

现有后端为Python/FastAPI、SQLAlchemy、Redis和RQ（requirements.txt登记redis 8.1.0、rq 2.12.0及FastAPI/Pydantic范围）；前端React 19、TypeScript约5.6、Vite 5、MUI 7，测试沿现有pytest与Vitest/Testing Library。本轮没有执行版本升级或运行时安装。上传持久state和工作稿由现有MySQL记录承载，Redis为任务/队列与缓存；不新建数据库表或更改标准科学键。目标为现有SC-Wiki服务链，不由本计划推断部署授权。

## 质量门

| 来源 | 必须保留的约束 | 本方案处理 | 当前证据边界 |
| --- | --- | --- | --- |
| AGENTS.md | mayuan、任务独立提交、不混入共享改动 | 仅本轮文档及原Spec待实施引用 | 运行时未修改 |
| #174/#203 | 稳定身份、局部写入、标准字段锁 | 问题为运行元数据；四宿主和三项契约列入任务 | 未进行实现验收 |
| #220/#221/#226 | 颜色/侧栏唯一规则、人工资料与审核分离 | 只引用原入口，不在新Spec自定消红或放行 | 不宣称已接通 |
| #192 | 当前工作与正式交接分开 | 仅采用的人工依据进入原字段/交接快照 | 不建立永久中间历史 |
| 用户修正 | 四目标、默认开、新文献、本文结构保留 | FR与任务覆盖；无重复解析对照 | 已确认方案，工程全文待审 |
| 远程文档 | 实际文件可访问才算双向链接 | Issue只列本地路径与待验证 | 未推送，远程门未通过 |

## 文档结构

本目录包含spec.md、plan.md、research.md、quickstart.md、tasks.md、checklists/requirements.md及建档检查analysis.md。另有data-model.md及contracts/questions.md，接口均为拟新增/变更，不宣称可调用。

## 源代码与文档触点

- `backend/ingest/human_questions.py（拟新增）`
- `backend/ingest/material_batches.py`
- `backend/ingest/upload_tasks.py`
- `backend/ingest/model_runtime.py`
- `backend/ingest/manual_evidence.py`
- `backend/ingest/field_decisions.py`
- `backend/api/upload_tasks.py`
- `frontend/src/components/UploadHumanQuestions.tsx（拟新增）`

**结构选择**：human_questions.py负责问题生命周期和指令边界；material_batches.py负责局部进度；现有保存与证据仍为唯一写入链。

## 需求到设计及任务映射

| 来源 | 组件/设计 | 任务 | 验证 |
| --- | --- | --- | --- |
| FR-001、FR-002 / SC-001 | human_questions.py按对象、版本、冲突来源身份追加去重 | T001、T002 | 两个冲突、同题改写、同字段不同冲突 |
| FR-003、FR-007、FR-009 / SC-001、SC-002 | material_batches.py按稳定身份记录已完成/待答项；model_runtime.py在安全点消费答案 | T003、T004 | 前组待答后组保存、真实依赖暂挂、技术失败停止 |
| FR-004、FR-005 / SC-002 | UploadHumanQuestions.tsx可复用交互组件，contracts/questions.md规定三类入口与暂不处理 | T005、T006 | 点击/人工填写/不答/进一步查证交互 |
| FR-006、FR-010 / SC-004 | manual_evidence.py、field_decisions.py、model_review.py只传递相关human_context；workdrafts/handoffs沿原链 | T007 | 人工方向与反证保存及正式交接重读 |
| FR-008 / SC-003 | 任务持久状态、队列revision与原执行代次；答案幂等，读写失败可恢复 | T002、T008 | 首题无草稿、重启、Redis丢失、重复、迟到和权限反例 |
| 全部FR / SC-005 | 后端、四宿主共享证据契约及性能回归 | T009、T010 | 三项契约、真实RQ停止/重新领取、局部/全链边界单列 |

## 阶段与依赖

1. 对照原文、旧Spec与实际源码，保留用户新旧取舍。
2. 先写能检出实际边界的失败回归，再串行实施本单元。
3. 完成局部检查、相关回归和实际范围留证；实现后才回写当前功能。
4. 共用upload_jobs.py、upload_tasks.py、model_review.py的改动依#238→#239→#240顺序串行；不并行覆盖共享文件。

## 复杂度说明

只增加任务问题协议和必要的局部恢复，不引入另一个Agent编排器、数据库或全表状态框架；持久化首题、版本和精确依赖是防丢失/串字段所必需。所有设计是后续实现方案，本轮不触发运行环境变更。


## 2026-11-12 实施补充

同一次模型结果显式给出resolution，原生request_human_question与最终human_required共用同一窄路由；不按理由文字猜科学结论，不另调分类模型。问题仅目标及原review_dependencies闭包暂挂。队列SQL先提交，任务保存合并最新revision；未发送的逐题草稿按task/actor/question/prompt版本存于sessionStorage。答案先持久接受，再经原模型/RQ恢复；相关资料沿ScientificManualEvidence保存，无科学approve。材料检查点允许待答前组和完成后组共存。无关题追加不使旧题版本失效，见contracts。

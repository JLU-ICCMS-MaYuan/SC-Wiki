# 实施计划：默认启用人工问题窗口并以最小改动接入新文献解析

**Issue**：[240](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/240)；**日期**：2026-11-11；**规格**：[spec.md](spec.md)。已按spec.md末尾本轮实施授权接线；具体已验证事实与未完成业务范围见validation.md。

## 摘要

正式接入和默认能力：在统一调度入口、任务公开DTO和红框挂载模块；测试关闭仅作为必要回归，不作同文献重复解析对照。

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

本目录包含spec.md、plan.md、research.md、quickstart.md、tasks.md、checklists/requirements.md及建档检查analysis.md。另有data-model.md及contracts/integration.md，接口均为拟新增/变更，不宣称可调用。

## 源代码与文档触点

- `backend/rag/config.py`
- `backend/ingest/upload_jobs.py`
- `backend/ingest/upload_contracts.py`
- `backend/api/upload_tasks.py`
- `frontend/src/components/UploadModelActivity.tsx`
- `frontend/src/pages/UploadPage.tsx`
- `frontend/src/components/UploadParsingDetail.tsx`
- `frontend/src/lib/paperProcessing.ts`
- `frontend/src/i18n/zh/upload.ts`
- `frontend/src/i18n/en/upload.ts`

**结构选择**：在统一调度入口、任务公开DTO和红框挂载模块；测试关闭仅作为必要回归，不作同文献重复解析对照。

## 需求到设计及任务映射

| 来源 | 组件/设计 | 任务 | 验证 |
| --- | --- | --- | --- |
| FR-001、FR-004 / SC-001 | upload_jobs.py、upload_contracts.py、upload_tasks API、UploadModelActivity/UploadPage正式挂载 | T001、T002 | 真实宿主产生问题、处理其他字段及局部恢复 |
| FR-002、FR-003 / SC-002 | RagSettings单一默认true开关，API提供能力，已有队列继续可处理 | T003、T004 | 未设置/开启/关闭、API与Worker一致、旧题可答 |
| FR-005 / SC-003 | 任务代次、轮询终态、耗时和清理复用#224，不变更并发 | T002、T005 | 不重复领取、等待不自动清理、实际执行时间不计人工等待 |
| FR-006、FR-007 / SC-004 | 直接新文献真实链路验收与README/Overview实现后回写 | T006、T007 | 不删旧稿、不安排开关对照、真实来源和模型留证 |

## 阶段与依赖

1. 对照原文、旧Spec与实际源码，保留用户新旧取舍。
2. 先写能检出实际边界的失败回归，再串行实施本单元。
3. 完成局部检查、相关回归和实际范围留证；实现后才回写当前功能。
4. 共用upload_jobs.py、upload_tasks.py、model_review.py的改动依#238→#239→#240顺序串行；不并行覆盖共享文件。

## 复杂度说明

只增加任务问题协议和必要的局部恢复，不引入另一个Agent编排器、数据库或全表状态框架；持久化首题、版本和精确依赖是防丢失/串字段所必需。所有设计是后续实现方案，本轮不触发运行环境变更。


## 2026-11-12 实施补充

同一次模型结果显式给出resolution，原生request_human_question与最终human_required共用同一窄路由；不按理由文字猜科学结论，不另调分类模型。问题仅目标及原review_dependencies闭包暂挂。队列SQL先提交，任务保存合并最新revision；未发送的逐题草稿按task/actor/question/prompt版本存于sessionStorage。答案先持久接受，再经原模型/RQ恢复；相关资料沿ScientificManualEvidence保存，无科学approve。材料检查点允许待答前组和完成后组共存。无关题追加不使旧题版本失效，见contracts。

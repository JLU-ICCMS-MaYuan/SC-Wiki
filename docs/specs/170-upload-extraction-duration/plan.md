# 实施计划：上传解析用时

**Issue**：[#170](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/170) · **日期**：2026-10-28 · **Spec**：[spec.md](spec.md)

## 摘要
服务端在现有状态事务中累计实际运行区间，前端复用列表时钟显示，并定期获取真实终态。

## 技术上下文
- 语言：Python 3.12.14（项目Conda运行时）、TypeScript 5.6、React 19。
- 依赖：FastAPI、Redis/RQ、MUI 7、Vite 5。
- 存储：Redis任务与已有科学草稿状态快照；无数据库迁移。
- 测试：pytest、Vitest/jsdom、Playwright真实页面隔离API；前端生产构建。
- 平台：现有浏览器与后台Worker；最多100条任务，用单个1秒时钟及3秒批量轮询。
- 约束：mayuan分支、保护其他任务修改、只提交本次文件、不推送或部署。

## 质量门
| 来源 | 要求 | 满足方式 | 状态 |
| --- | --- | --- | --- |
| 用户确认 | 起止及暂停口径 | spec FR-002/003与状态转换一致 | 通过 |
| AGENTS.md | 本次范围提交 | 显式路径与暂存差异检查 | 实施后核验 |
| Spec | 不虚构旧数据 | 缺失字段降级，明确重试才初始化 | 通过 |
| Skill | 远程双向链接 | 本地实施已授权，未推送保持Issue开放 | 待发布验证 |

## 文档与源代码结构
本目录包含Spec、Plan、Research、数据模型、接口契约、Tasks、quickstart及需求检查。
- backend/ingest/upload_contracts.py：状态转换、公开字段。
- backend/ingest/upload_tasks.py：新任务初始化。
- frontend/src/lib/paperProcessing.ts：可选类型。
- frontend/src/lib/uploadExtractionTiming.ts：校验与显示秒数。
- frontend/src/components/UploadTaskCenter.tsx：布局、秒级显示、状态轮询。
- frontend/src/i18n/{zh,en}/upload.ts：文案。
- tests/01_decentralized_uploading/test_upload_extraction_timing.py：状态/存取边界。
- tests/01_decentralized_uploading/upload-extraction-timing.test.tsx：页面行为。
- tests/01_decentralized_uploading/upload-extraction-timing-browser.mjs：浏览器验收。

## 需求到设计的映射
| 来源 | 设计责任/数据事实 | 任务 | 验证 |
| --- | --- | --- | --- |
| FR-001/006、SC-004 | 列表布局、纯显示函数与字典 | T003/T005/T006 | 中英文/窄屏/历史数据 |
| FR-002/003/005、SC-001/003 | 后端状态契约，累计区间 | T002/T004 | 暂停/恢复/终态/重试测试 |
| FR-004、SC-002 | 服务端持久状态及只读列表轮询 | T002/T003/T004/T005/T006 | 刷新/编辑/迟到响应 |

## 阶段与依赖
先文档与测试，再后端、前端，最后浏览器/构建/总览/提交。单个P1故事即MVP，不新增下游功能。

## 复杂度说明
累计区间是排除人工等待所必需；单纯结束减开始不符合需求。只用一个列表轮询，不新增每任务请求或数据库表。

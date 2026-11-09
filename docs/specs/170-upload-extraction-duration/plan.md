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

## 2026-11-09：US2 token记录与显示

用户已对完整草案答复“开始”，授权FR-007～011、SC-005～008及本计划的必要实现。

- 数据所有权：后台维护可选extraction_token_usage与私有请求去重记录，随现有Redis状态事务和受保护快照保存；不改科学表单键或数据库结构。
- 真实回执：在统一LLM流式请求实际发送处记录开始/结束，读取usage；上下文摘要的LangChain请求复用同一收集器并读取usage_metadata。申请各模型流式用量回执，不另发模型调用。
- 轮次与幂等：新任务及retry=True创建独立run_id；暂停/继续不重建。每次物理请求有独立request_id，开始计请求数，结束最多计量一次；缓存/检查点不发送新请求即不新增计量。旧执行受#224代次检查及run_id隔离，未完成回执保留为不完整统计。
- 一致性：请求事件通过现有update_state的WATCH事务聚合；开始即持久记录，使Worker中断仍能识别缺失用量，不仅在finally汇总内存日志。终态发布前各正常请求已经完成计量，刷新恢复沿现有读路径。
- 展示：UploadTaskCenter在用时旁显示总量，明细用可访问的提示展示；现有状态读取更新token，不新增轮询。容器允许换行，历史缺失与部分缺失分别提示。
- 聚合规则：支持prompt_tokens/completion_tokens及input_tokens/output_tokens；只有非负整数且总量一致的完整回执才计入。total_tokens缺失时可由实际输入与输出相加；缓存/推理细项不再叠加，非法/不完整回执作为缺失。

| 需求与成功标准 | 数据事实/职责 | 任务与验证 |
| --- | --- | --- |
| FR-007/011、SC-005/008 | 公开DTO、前端校验与中英文字典 | T009/T012/T013：实际组件、浏览器、窄屏及旧计时回归 |
| FR-008、SC-005/008 | SDK流式usage与摘要usage_metadata | T009/T010/T014：真实HTTP/SSE、重试/非法输出/缺失及真实服务回执 |
| FR-009/010、SC-006/007 | 状态事务、轮次/请求去重、#224代次隔离、现有快照恢复 | T009/T011/T014：存取/SQLite恢复、停止续跑、检查点及旧回执 |

按T008→T009→T010/T011/T012→T013/T014→T015实施；各步串行执行，无代理委派。只更新本次明确文件，保留其他任务工作区修改，不推送、不部署。

已查明自动谱backend/spectra/vision.py与原生PDF backend/ingest/native_pdf.py绕过统一JSON入口，T010/T014同时覆盖这两处实际SDK边界；Responses实际用量使用input_tokens/output_tokens。仅补全已确认的本轮自动解析消耗范围，不修改科学输出规则。

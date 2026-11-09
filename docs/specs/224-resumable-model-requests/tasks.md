# 实施任务

输入：[Spec](spec.md)、[Plan](plan.md)、[Research](research.md)、[数据模型](data-model.md)、[接口](contracts/runtime.md)。协作状态以Issue为准。

- [x] T001 准备：归档原图与需求，核验依赖，建立失败回归backend/tests/test_model_runtime.py、test_model_memory.py。
- [x] T002 US1 实现backend/ingest/model_runtime.py与backend/rag/llm.py的单次调用、持续重试、动态及失败归档。
- [x] T003 US2 实现upload_contracts.py、upload_tasks.py、api/upload_tasks.py的停止/继续/保留/权限/代次保护。
- [x] T004 US2 接入upload_jobs.py完整调用检查点与原文提取复用，保护当前草稿和迟到写回。
- [x] T005 US3 接入backend/ingest/model_memory.py及requirements.txt中的真实LangMem；验证滚动摘要与配对/科学依据保护。
- [x] T006 US1 接入UploadModelActivity.tsx及唯一动态区，停止/继续交互与真实日志、错误展示。
- [x] T007 执行后端/字段/四宿主表单/变异/构建及真实PDF模型，保存独立证据，更新旧Spec、Overview、README。
- [ ] T008 继续Peng2017真实五阶段；未完成单列，不把局部通过写成完成；合理验证后按任务范围本地提交，不推送。

依赖：T001→T002→T003→T004；T005依赖基础调用，T006依赖接口；T007覆盖全部生产链路，T008以真实业务状态判定。

## 本轮证据与边界

T001—T006证据：59项后端（含真实HTTP/SSE、检查点、停止／日志／权限）、21项上传交互；原生Safari同任务停止继续及完整响应复用、LangMem真实摘要见validation.md。T007的既有门已通过，仍待隔离最终源码复核；T008正式五阶段未完成。暂停／续跑验收旧任务已留存332个产物、112872343字节，并通过网页仅清理该未送审旧任务；随后原哈希重传。

T007最终隔离复核已通过，证据：request-runtime-224/isolated-*.txt及本地提交84c06397。T008仍未完成，新上传d2ca41e5f16b4d65bf744f5d5325e855在上游503持续重试，不能把T007代码验证计作正式科学保存或五阶段通过。

- [x] T009 补齐固定输入的来源目录/结构共享组合、短来源身份、多重预算、显式结构契约及稳定来源顺序。失败先检出；120项定向通过、2项隔离MySQL条件跳过，四宿主225、12项变异、字段契约与构建通过；实际生产隔离整理链53状态、31结构、无生成问题。逐字段科学复核、引用匹配、谱和角色交接由T008真实网页继续，不能算作本任务已验收。

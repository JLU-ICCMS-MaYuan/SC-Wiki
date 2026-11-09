# 验证记录

日期：2026-10-28；关联 [Issue #170](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/170)。

## 已通过
- 新增后端测试12项：运行区间、上传/排队排除、角色等待与恢复、终态幂等、重试独立、旧任务降级、角色恢复入队失败、Worker未开始即失败、重复阶段事件，以及生产create/update/get/公开DTO和SQLite受保护草稿快照恢复。
- 连同既有契约/清理回归中修改前已通过的15项，共27项通过。8项既有失败逐项核对与本次修改前完全一致，详见 [基线对比](assets/baseline-comparison.json)。
- Vitest 16项通过：新增10项与现有单条清理2项、批量删除4项；包含实时推进、自动取得终态、暂停恢复、刷新与重开、重试、缺失/损坏数据、迟到响应、中英文及选择交互。
- TypeScript检查和Vite生产构建通过；构建仍有既有大分包提示。
- Playwright使用生产构建的真实 `/upload` 页面，API全部隔离，时间数据通过Python生产状态转换生成。1440px中文、390px中文与390px英文均通过实时、终态冻结、重开、角色等待、历史降级、长文件名布局、选择与取消验证；无页面异常或未预期API。
- 已人工查看三张截图：宽屏标题旁同排，窄屏换行，用时不被长文件名挤出。截图含测试账号/模型夹具，不是实际业务数据。

## 环境与边界
使用项目Python 3.12.14与Node 22.21.1；系统Node 26的实验性localStorage导致原有和新增Vitest一起失败，换用项目运行时后全部通过。测试专用JWT值只传入测试进程，不读取真实密钥、不修改系统配置。

既有8项失败涉及旧manifest角色约束、清理上下文、旧提交/审核快照接口；相同进程环境下加载修改前两个模块仍为相同失败，未扩大本次需求修复它们。不是全仓库测试通过声明。

Redis存取测试替代外部传输、保留真实生产入口；受保护快照恢复使用SQLite实际保存读取。浏览器接口隔离，不代表真实模型、MySQL或生产PDF解析服务端到端验收。未部署、未推送、未回填历史任务。

## 证据
- [桌面中文](assets/zh-1440.png)
- [窄屏中文](assets/zh-390.png)
- [窄屏英文](assets/en-390.png)
- [浏览器结果](assets/result.json)

## 关闭边界
Issue与本地Spec已关联，远程Spec/图片尚未推送，不能声称远程双向链接验证完成，Issue保持开放。

## 2026-11-09：token记录与显示

本节仅对应新增US2，不改写2026-10-28原计时验证结果。用户阅读完整Issue/Spec草案后以“开始”授权本次实施。

### 结果与证据

- 新增17项后端token用例；与原计时、统一LLM、#224运行器/摘要、原生PDF及谱回归合计123项通过。覆盖真实OpenAI SDK/HTTP/SSE用量读取、主Worker收集、自动谱入口、非流式读图、Responses PDF、JSON失败已耗用量、请求缺失、重复回执、停止/继续、新轮与旧代次隔离、传输重试、检查点复用及SQLite快照恢复。
- 前端用时/token组件18项及批量删除4项，共22项通过；四宿主表单契约225项通过，12项变异回退全部检出，科学字段契约v1检查通过。未新增或更改科学字段键。
- TypeScript/Vite生产构建通过，保留既有大分包提示。无需为本次运行指标改变科学表单或新增数据库迁移。
- 实际生产构建页面的3组隔离浏览器场景通过：1440px中文、390px中文、390px英文；覆盖总量、键盘可读取明细、未记录/不完整、真实用量卡片、刷新冻结、原计时、长文件名、选择与取消，无页面异常或意外业务API。已查看三张完整页面截图。
- 真实deepseek-v4-pro合成验证请求一次：服务返回输入39、输出5、总计44；生产收集后的任务聚合逐项相等，清除隔离Redis缓存后SQLite恢复一致，页面显示44并展示39/5明细。未输出或留存密钥。
- 实施前先确认新增能力能失败：后端模块缺失失败；前端8项新场景失败而原10项通过；发现非流式读图/原生PDF直连入口后，两项漏计反例先失败再接通。构建发现LanguageContext字段名错误已修正，最终构建通过。

结构化结果：[验证汇总](assets/token-usage/validation-result.json)、[真实回执与源码摘要](assets/token-usage/live-usage.json)、[真实请求的公开任务](assets/token-usage/live-task.json)、[浏览器检查](assets/token-usage/browser-result.json)。截图：[桌面中文](assets/token-usage/zh-1440.png)、[窄屏中文](assets/token-usage/zh-390.png)、[窄屏英文](assets/token-usage/en-390.png)。

### 复现方式

- 后端：项目Conda的python -m pytest，路径为test_upload_token_usage.py、test_upload_extraction_timing.py、test_issue114_native_pdf.py与backend/tests下test_spectra.py、test_model_runtime.py、test_model_memory.py、test_llm.py、test_llm_request_paths.py、test_llm_client_coverage.py、test_parsing_workflows.py；隔离DATABASE_URL=sqlite:///:memory:与测试JWT。
- 前端：项目Node运行Vitest的upload-extraction-timing.test.tsx与upload-task-batch-delete.test.tsx；执行npm run build、test:form-contract、test:form-contract:mutation、test:field-contract --prefix frontend。
- 真实模型：项目Python执行tests/TestForRealScenario/upload-token-usage-live.py --output /tmp/scwiki170-token-live；仅读取当前默认模型配置，任务/Redis传输/SQLite均隔离，验证请求只发一次。
- 浏览器：运行upload-extraction-timing-browser.mjs，设置TOKEN_USAGE_FIXTURE=/tmp/scwiki170-token-live/live-task.json、TIMING_TEST_OUTPUT与项目Python/Playwright模块路径。

### 范围与限制

测试在当前mayuan共享工作树执行，其他任务修改保留；提交前核对暂存字节与已验证文件相同，仅纳入本次范围。真实模型请求使用合成内容，不代表整篇原PDF科学字段重新提取；本次仅增加运行用量记录，未改提取、科学值或输出契约。Redis只隔离传输，SQLite真实读写；未宣称MySQL、完整PDF或生产部署验收。未推送、部署、历史回填，远程Spec链接门仍未完成，Issue保持OPEN。

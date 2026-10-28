# 验证记录

日期：2026-10-28，Asia/Shanghai。关联 [#172](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/172)。

## 结论与边界

本次定位的结构读取崩溃已修复；声子方法自动名称统一，后台计算阶段及人工名称保留。新提取边界不接受含义不明的分组、非对象数组项及缺少阶段的已知条件扩展。既有条件原文检查和 `_read_chunk` 重试实现未修改。

真实字段重跑成功，不代表整篇 CaH6 解析、全篇覆盖门、MySQL 正式提交或浏览器端到端全部通过。没有修改或重新排队原业务任务，没有批量改写历史草稿，没有推送或生产部署。

## 修改前后测试

新增测试的初次有效后台运行：20 失败、4 通过，包含真实字符串 `.get` 异常、null 扩展崩溃和未校验格式；前端 2 失败。实现及补充现场反例后，新增后台 35 项通过，前端 2 项通过。

最终定向后台回归：152 通过、3 项已确认基线失败的测试不纳入通过数，见 [后台输出](assets/backend-tests.log)。包含真实 Worker `_read_chunk` 边界（已知分组成功、未知格式仍按既有一次纠错后失败）、来源过滤、参数契约、材料组装及侧栏字段名。

前端相关 6 项通过，覆盖表单声子方法编辑、序列化保存重开、后台阶段/来源保留、人工名称不覆盖及既有参数表单，见 [前端输出](assets/frontend-tests.log)。`npm run build` 通过 TypeScript 与 Vite 生产构建；只有现有 3Dmol eval、大包体积警告。未执行新的浏览器端到端测试。

`git diff --check`、Python 编译、Spec 本地相对链接、截图解码与 SHA-256 均通过。

## 基线失败的独立核对

在不含本次修改的 `a005c11613b472bc11e80dc125442d92c0cecd95` 的 backend/tests Git 归档副本中，以下三项以同样断言失败，见 [基线输出](assets/baseline-tests.log)：

- test_one_bounded_repair_preserves_original_response：预期两次调用，实际一次。
- test_bounded_repair_does_not_swallow_upload_cancellation：未触发测试预期的第二次调用取消。
- test_new_upload_rechecks_final_filled_conditions：预期空值先被核对，实际仅核对补入值。

这些失败发生于未改动的核对流程；本次不修改重试策略，不修订测试预期来伪造通过，也不声称全仓测试通过。

## 本次真实失败响应的重放

输入是原任务 `29b2dd4604b64ee58c669c0efddb8cab` 已归档的 `8746eb438a36477e9889ac9427bbebcd/raw.json` 和相邻 input.json。最终证据目录 `.data/issue172-replay-verified/`。

正式 `normalize_extraction → merge_scientific_candidates → _normalize_draft → save_draft → get_draft` 通过，保留 6 条记录、Redis 隔离影子草稿保存重读一致。原始输入哈希前后相同。

格式整理确实保留了原响应的 DFPT 候选；后续既有原文检查因所引 SI 段落未直接出现 DFPT 而剔除该候选。这是证据检查的结果，不是格式转换丢值，不强行让它变成正式事实。原始响应和转换前候选均留档；有明确来源的分组转换保留测试通过。

## 从真实来源重新提取字段

模型：server:LLM1 / deepseek-v4-pro。复用同一上传文件的 IR，核对 IR source_sha256 与任务文件清单一致：正文第 1、4 页，补充材料第 2、3 页，页面完整块未截断。仅重新提取一个 CaH6 Tc 记录的必要上下文，以及声子方法、软件、泛函；未重提整篇其他字段。

重新调用正式 `complete_json`，使用正式互补提取提示和契约，仅追加字段输出范围；未注入预填科学答案。之后运行生产标准化、方法/原文检查、科学记录组装、草稿转换、正式 save_draft/get_draft 的 Redis 影子路径；新建的临时键清理，业务原任务只读。

最终 `.data/issue172-live-3/` 运行用时 81.582 秒：

| 字段 | 保存重读结果 |
|---|---|
| 声子方法 | density functional (linear-response) theory |
| 软件 | QUANTUM ESPRESSO |
| QE 泛函 | null，未由 VASP 的泛函推断 |

原文依据随记录保留，最终方法与格式整理前相同，保存重读逐值相同。来源页、上传身份哈希及被验证源码 SHA-256 见 [精简验证证据](assets/field-verification-summary.json)。完整输入、模型响应和草稿仅在本地 `.data`，不提交。

## 失败尝试与验证修正

- live-1：模型把软件及 PBE 放入无阶段扩展，原有过滤漏过；首版验证脚本只检查固定软件字段，也错误标为 passed。此报告原样留存并附 audit.md 明确作废；本次实现补上阶段校验，脚本同时检查固定字段与扩展，原 live-1 响应在 `.data/issue172-unscoped-rejection/` 被明确 ValueError 拒绝。
- live-2：模型将原文长名称换成 DFPT，字段被原文检查剔除，验收明确失败。没有放宽科学检查；提示要求保留原文的方法名称，新增对应正反例，再从来源重新提取。
- live-3：通过上述全部字段断言，以此作为最终真实验收依据。没有修改前两次原响应或用它们冒充通过结果。

## 需求覆盖与交付

FR-001/002、SC-001：前端编辑重开与后台侧栏名称测试；FR-003/004、SC-002/003：固定响应、33 项结构/字段测试和 Worker 边界；FR-005、SC-004：QE 原文正反例及无阶段绕过反例；FR-006/007、SC-005：实际字段重跑、保存重读与 AGENTS.md 新规则。另有 2 项原文长名称与不支持缩写测试，新增后台共 35 项。

Spec、Plan、Research、数据约定、契约、Tasks、需求检查和上传 Overview 已同步。Issue 保持 OPEN：远程 Spec 尚未推送，双向远程链接待单独授权推送后验证；本地完成不冒充远程关闭门通过。

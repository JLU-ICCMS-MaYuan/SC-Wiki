# 验证记录

## 已完成的代码验证

本机实时开发环境，分支 `mayuan`；未推送、未部署到远端。以下测试使用当前工作树，最终提交时仍须核对文件摘要，不能把并行 #225 的修改混入本单元。

| 验证 | 实际结果 | 本机证据 |
| --- | --- | --- |
| 改前反例 | 无证决定5项、四宿主8项、后台持锁写回2项失败 | `.local/issue226/baseline-{waiver,hosts,mysql}.log` |
| 必需完整表单门 | 16文件225项通过 | `.local/issue226/form-runtime24.log` |
| 故障注入 | 8项渲染回退、4项原免审漏红均被检出 | `.local/issue226/mutation-final.log` |
| 固定科学字段契约 | v1摘要及21论文字段、11材料字段、3软件组通过 | `.local/issue226/field-final.log` |
| 后端决定、资料及相邻回归 | 68项通过 | `.local/issue226/backend-final.log` |
| 真实隔离MySQL并发、权限及批准事务 | 20项通过 | `.local/issue226/mysql-publish.log` |
| Go持久化及读取 | 相关包定向回归通过 | `.local/issue226/go-final.log` |
| 最后侧栏调整的相邻回归 | 3文件23项通过 | `.local/issue226/workflow-final.log` |
| TypeScript及Vite构建 | 通过；保留既有分包大小提示 | `.local/issue226/build-final.log` |

多源联合输入测试执行正式 worker、PDF读取和图片投递边界，模型与公网链接读取采用固定响应，以覆盖通过、不通过、取消和技术失败；不能据此声称真实模型认定某项科学内容正确。用户给定 AIP 链接实际返回 HTTP 403，记录为未读且零模型调用，见 `.local/issue226/live-link.json`。真实 URL 可达性不保证，失败必须可见。

完整宿主文字／数字设置新增反例在修复前4项均失败（`(current || []).map is not a function`），修复后包含该反例的15项通过，见 `.local/issue226/scalar-before.log` 与 `scalar-after.log`。该问题属于本轮统一编辑器对非列表类型的实现缺陷，未改变旧需求。

系统Node26.9.0的Web Storage全局导致12项旧审核测试在渲染前失败，未改源码副本同样12项失败；Node24.19.0下该12项及完整16文件225项均通过。分别保留 `review-actions-baseline-node26.log`、`review-actions-runtime.log` 与 `form-runtime24.log`，没有删测试、改断言或增加超时。

## CaH6正式页面黑盒：结构家族阶段通过

使用本机1208第二次送审稿及 `superadmin_mayuan`，Chrome正式页面/API，不替换接口、不直接修改数据库状态：

- 5个CaH6状态的结构家族为“笼型结构”；9个其他Ca–H状态的结构家族清空。
- 14项均通过明确的无资料人工按钮保存，界面显示黄色，决定为 `mode=without_evidence`，零模型任务。
- 提交前800个字段中无阻断；其余786项当前值SHA与操作前一致，不为凑齐资料另改科学值。
- 本轮包括低压CaH6状态，均按用户明确指令作人工决定，不宣称全部经模型或原文科学验证。
- 现场记录：`.local/issue226/blackbox/families.json`、`family-yellow.png`、`preapprove.json`；仅值/历史摘要见 `.local/issue226/blackbox-before.json`，不是可恢复整稿备份。

## 尚未完成：新版批准与搜索

正式点击“审核通过并发布”，提交检查返回200，`review-commit`返回500。日志为 `Unknown column 'paper_references.match_evidence'`：并行 #225 新代码已加载，但本机数据库尚未执行其迁移。批准事务回滚，旧公开版与历史保持，14项黄色仍在当前工作稿。不得把原 `approved_revision=1` 的旧版当成本轮批准成功。

现成 #225 迁移在独立空业务行临时库演练通过：两项可空JSON列、新缓存表及匹配方法约束扩展，既有夹具列摘要不变，临时库已清理；演练没有业务库写入或私有备份。详情见 `.local/issue226/migration225-rehearsal.json`。按 #225 Plan 的“业务环境执行不默认为已授权”，已向用户询问本机执行授权，目前等待答复；尚未应用业务库迁移。

待授权解除阻塞后，继续正式页面批准、当前稿释放、新批准版和冻结重读、旧历史摘要保持、14项黄色及其他786项值保持，以及正常网站搜索。未完成前 SC-005/T008 不勾选，整体交付不宣称完成；远程Spec未推送核验，Issue保持OPEN。

已精简归档正式页面截图、14项操作回执、提交前摘要及失败回执，见 [验证附件目录](validation-assets/receipt.json)。不复制整稿或PDF，不创建业务恢复备份。

## 2026-11-10 分类提交前复核

在 `mayuan` 当前源码上重新验证，Node 使用本机已有的 24.19.0：完整表单16文件233项、人工资料交互3文件18项、12项故障注入、固定科学字段契约、Go两项人工决定回归及 TypeScript/Vite 构建均通过。构建保留既有大分包提示。

后端7文件83项通过，4项失败；将未修改的 `157c0de266fb34dacd5c669c87b89e3d8fdfe865` 导出到独立临时目录，同一测试环境复现以下同名、同错失败，不计入本轮通过项：

- `test_transfer_rechecks_explanation_after_preflight`：未抛出预期的 `ManualEvidenceError`。
- `test_pdf_is_validated_and_only_actual_review_marks_it_read`：未抛出预期的 `ValueError`。
- `test_reviewer_reason_does_not_overwrite_uploader_evidence`：当前核对上下文的资料提交者集合为空，断言预期为 `{7}`。
- `test_patch_rejects_concurrent_change_without_overwriting`：未抛出预期的 `HTTPException`。

本次仅修正旧测试夹具缺少的核对／来源表、过时的无证说明放行及文件数量断言，以及前端字段详情接口的模拟响应；未改业务逻辑、删除测试或放宽断言。相关用例继续验证真实证据、每类10项限制及保存失败保留输入。日志摘要和提交前源码摘要见 [本次复核附件](validation-assets/commit-check.json)；原 `source-snapshot.json` 保留为此前验收时的历史源码，不覆盖为当前版本。

本次未重跑真实模型、MySQL并发、正式CaH6批准或搜索；此前记录及其边界继续保留。四个旧失败、T008/T009和 Issue OPEN 状态不因代码分类提交被标为完成；不据旧记录判断当前业务库是否仍缺迁移。


## 2026-11-11 枚举选择未填写的真实保存

真实GPT草稿在字段设置选择“未填写”后返回400 form_contract_invalid：material_dimensionality枚举未登记。既有契约允许null，设置器却发送空字符串。只将枚举的显式“未填写”转换为null，不把unknown自动当空，不改科学键、权限或审核门。

四宿主真实交互新增回归先4次在value为空字符串的断言失败，修复后4通过；测试夹具缺真实field-detail及关闭过渡时机问题另存，不当作产品故障。完整表单250通过、12变异检出、字段契约及构建通过。真实Safari原任务d789acceee124022b3257f84780d1156重试后，state-65d239ce2d51b37badbe的维度重读为null；其他字段仍按真实局部改动保存。浏览器失败响应与enum-empty-assertion-before/after.log、form-contract-enum-empty.log等保留在本run。完整送审与批准继续进行，未计整篇黑盒通过。

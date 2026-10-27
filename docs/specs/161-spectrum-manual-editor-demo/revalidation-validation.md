# 材料条件失效后恢复编辑验收

日期：2026-10-27。用户“继续”确认本轮Issue/Spec增补稿后实施，对应FR-058至061、SC-033至034。

## 实现

- listing返回stale_reasons：历史、来源变化、材料删除、材料状态变化。详情按具体原因解释禁用，幅值待核对文本明确允许编辑/保存。
- 来源未变、同材料归属仍存在、有权限的当前谱提供“核对材料条件并继续编辑”。确认窗口展示当前已保存材料摘要和原图说明；取消不写入，确认不是幅值或科学采纳。
- POST revalidate核对用户权限/来源哈希/内容版本/集合版本/基础运行/state_key/当前同类最新集合，必须confirmed=true。仅材料签名变化可恢复，来源变化/材料删除/旧集合/重复确认/并发冲突拒绝。
- 新建不可变run，原样复制曲线、连线、标定、编辑文档和操作；旧运行保留。派生积分、候选和采纳撤回，记录内部作者/时间/原运行/旧新签名/材料摘要，公开接口不暴露此记录。
- 成功后更新详情URL，等待本版本原图加载后自动打开编辑器，避免使用已被撤销的旧blob地址。继续编辑、保存和主动重算均可；科学条件不足显示原因。

## 验证

- 前端61项通过：[日志](assets/revalidation-verification/frontend-tests.txt)。包括恢复入口条件、取消无写、提交携带展示版本、冲突保留窗口、来源/材料删除不提供恢复。历史页文案断言已同步为具体原因。
- 后端125项通过、3项并发测试在SQLite跳过：[日志](assets/revalidation-verification/backend-tests.txt)。α²F/DOS实际HTTP恢复前后点、标定、manual_documents逐字相同，旧run保持；来源/材料/权限/版本/历史/缺确认/重复确认拒绝，恢复后的编辑读取和重算可调用。
- [当前MySQL74项](assets/revalidation-current-mysql.json)通过，包含人工保存、重算和恢复确认的并发行锁验证。原16集合/57运行数量及逐行哈希不变；随机目标精确清理，无DDL。
- [恢复浏览器8场景](assets/revalidation-verification/revalidation/revalidation-browser-validation.json)通过：具体原因、确认信息/取消、409、重复点击、新版本自动打开、刷新/幅值未知仍可编辑、编辑保存重算、DOS分波/390px和原运行保留。真实React、正式HTTP和隔离SQLite，全部API重定向测试服务；409场景用故障注入，实际服务端冲突另由HTTP/MySQL验证。
- [定位7场景与重算8场景](assets/revalidation-verification/regression/browser-suite-summary.json)回归通过。
- 正式TypeScript/Vite构建通过：[日志](assets/revalidation-verification/build.txt)。既有3Dmol eval/大包提示仍存在。
- 已查看[恢复入口](assets/revalidation-verification/revalidation/revalidation-stale-with-action.png)、[材料确认窗口](assets/revalidation-verification/revalidation/revalidation-confirm-dialog.png)、[恢复编辑](assets/revalidation-verification/revalidation/revalidation-alpha-editor-unlocked.png)及[DOS窄屏](assets/revalidation-verification/revalidation/revalidation-dos-mobile-detail.png)。确认窗口截图等待过渡结束后归档。
- [Demo保护](assets/revalidation-verification/demo-protection.json)前后内容哈希一致，用户联动原文件未修改或纳入提交。

## 实际页面与边界

[只读核对](assets/revalidation-verification/current-spectrum-readonly.json)：截图300 GPa谱集合afd8723697e84425b75790cfbafb4862仍为版本5/run 069e542aba8e45dca77a60d5ba0b9d22，当前唯一失效原因state_changed、有编辑权，满足新入口前提。没有替用户确认或改写真实业务谱；需要用户对照图后在页面确认。本地开发服务OpenAPI已读取确认revalidate路由存在，没有重启/部署服务。

FR/SC映射：FR-058→listing与详情原因；FR-059/060→revalidate契约/不可变运行与数据一致测试；FR-061→权限/来源/历史/并发拒绝及Demo保护；SC-033/034→上述数值/HTTP/MySQL/浏览器证据。

本轮只修复材料失效恢复。先前全流程报告中的旧URL恢复V1至V4仍未改造，不绕开编辑版本保护。无数据库表变更、无AI重提取、无推送；Spec远程链接仍待推送后验证，Issue保持开放。

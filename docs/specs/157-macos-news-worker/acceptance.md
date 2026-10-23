# 实际恢复验收

## 故障证据

- 本地 API 本周三栏 0/0/0；全量 4/327/790，共 1121 条，最新发表内容停在九月。同期线上是 0/24/2，两套数据独立。
- 资讯 Worker 重复打印 NSCharacterSet initializeAfterFork 和 signal 6；随后所有来源 collection_busy。锁产生时间与最近一次崩溃 02:56:49 UTC 一致，核验时 Worker idle、started 注册表为空。
- 代码仅资讯入口仍使用 fork Worker，上传／社区已使用 macOS SpawnWorker。

## 处理与结果

1. 26 项平台、调度和采集回归通过。
2. 仅停止本地 news-scheduler、news-worker；确认无 Worker、无 started job、无采集进程后，按原值比较删除单一遗留锁。未清空 Redis 或队列，见 [锁恢复记录](assets/lock-recovery.json)。
3. 启动日志确认 `news worker implementation=SpawnWorker`。arXiv 作业正常结束，抓取 300 条，接受 262 条（包含重叠水位记录，不表示新增 262 条），成功水位从九月推进到 2026-10-23。
4. 本周本地 API 变为新闻 0、预印本 30、期刊栏 2；无模拟数据、无生产复制，保持原发表日期与筛选规则。[真实 API 快照](assets/recovery-api.json)。
5. Playwright 直接打开本机 `/news`，没有接口拦截，验证预印本和期刊栏首条真实标题可见，零脚本错误。截图留本地 `docs/local/news157/recovered-feed.png`，已实际查看。
6. 恢复后无运行中采集任务，collection-lock 不存在；正常调度与分类任务继续执行。

## 未恢复来源

- Google News：正常作业仍报 http_error；额外只读探测在默认连接与直连模式均 ConnectTimeout。新闻栏 0 只能表示未采到，不证明本周没有新闻。本轮不改网络配置或访问控制。
- OpenAlex：首轮正常重试失败；单次补充采集确认第一页 HTTP 200，游标下一页 HTTP 401 Unauthorized。按现有事务规则整批拒绝，不把第一页当成完整采集、不推进成功水位；本轮未规避授权限制。
- 这两项来源访问问题与本次 macOS 进程崩溃分开，保留在 Issue #157，不能宣称全部来源健康。线上未做任何修改。

## 交付边界

仅修复资讯 CLI 平台选择，保留原来源、过滤、分类和队列实现。其他任务的页面、登录、资料代码与数据库结构均未改动；未推送，远程文档链接仍待核验。

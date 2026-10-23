# 诊断与决策

日志 2026-10-23 10:56:49 的 NSCharacterSet initializeAfterFork 错误和 RQ signal 6，与锁 UUID 的产生时间 02:56:49 UTC 一致。每约 17 分钟崩溃一次，锁 TTL 1000 秒，其间其他来源报 collection_busy。核验时 Worker idle、无 started job。

只释放锁会在下次采集再次崩溃，必须适配进程模型。沿用项目已有 SpawnWorker，不设置绕过系统安全检查的环境变量，不升级 RQ。

同刻线上本周有 24 条预印本、2 条期刊栏内容；线上 Google News/OpenAlex 的来源错误与本地 macOS 崩溃分开记录。

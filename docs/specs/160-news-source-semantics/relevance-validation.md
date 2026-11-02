# 富氢候选与模型相关性增量验收

## 已实现范围

2026-11-02，按用户在 #160 增补后完成的授权，扩大期刊发现词、保存收录前候选、增加默认 LLM 三态判断与短批恢复。研究标签仍在公开收录后执行；新闻、预印本、自然周及历史契约保持。本轮未改变任何业务运行环境。

## 核验结果

- 资讯 Python 专项101项：采集、出版社、调度、原有研究分类、新相关性和服务拆分契约。新增覆盖真实 DOI、扩词、待判保留、只发布相关、重复采集、信息补充、跨源合并、失败三次、租约中断、旧结果、规则更新、事务回滚与队列公平性。
- 独立 MySQL/Redis 进程、全新 news_test_relevance 库：新迁移升级/降级/再升级、三态存储、真实 RQ SimpleWorker、Python发布后Go全部资讯专项通过。只一个相关条目公开，其他两个候选不进入总数，内部摘要不公开，旧日期进入历史，科研哨兵行不变。证据：assets/verification/relevance-mysql.txt。临时服务和数据库已清理。
- 实际生产采集器只读 Crossref 查询 superhydrides：窗口2026-10-03至11-02，返回3条，命中目标 DOI；未写业务库。单数 superhydride 控制查询返回0条。证据：assets/verification/relevance-live-discovery.json。
- 服务端默认模型 deepseek-v4-pro：真实铯论文输入加6个合成边界，共7例重测通过。真实论文只有题名摘要，最终 insufficient；直接超导为 related，一般制氢/纯储氢/背景提及/提示注入为 unrelated，无摘要富氢结构为 insufficient。证据：relevance-live-model.json；首次模型过推断记录另存 relevance-live-model-initial.json。未使用截图正文，不以Mock测试代替语义检查。
- 原图 IMG-003 已按原始字节归档并核验，索引 assets/images.json；附件仅为调查材料。

## 并行工作与验证限制

共享工作区另有材料字段变更，Go测试曾因 MaterialState 的 PressureMinGPa/PressureMaxGPa/PressureRaw 字段缺失而编译失败。因此在已提交基线 dcd07a29 加本次文件的独立源码副本中验证，未修改其他任务；不是宣称共享工作区整套测试通过。后续另一个资讯分页任务修改了同一Go测试文件及页面；本次按已验证快照仅提交新增候选隐私测试，该任务的分页修改保留在工作区，不纳入本次提交。隔离副本仅当前任务迁移时为单头20261102_0160；并行 #203/#204 未提交迁移的组合合流需在部署前协调。

首次临时MySQL库使用不同排序规则，与旧分类外键不兼容；将测试库统一为旧表默认utf8mb4_0900_ai_ci后继续，新候选迁移没有外键。此为测试环境修正，没有修改旧业务迁移。

本轮未新增前端布局，未重复浏览器视觉验证；Go实际接口契约验证公开计数与字段边界。未进行无Key OpenAlex完整翻页，不承诺期刊覆盖率。信息不足不会自动下载全文或变成公开文章；需等待上游元数据补充。业务迁移、历史回填、重启、部署及Git推送均未执行。

## 复现

项目Python环境中执行：

```sh
DATABASE_URL=sqlite:// python -m pytest tests/07_researcher_community_forum/test_news_collection.py tests/07_researcher_community_forum/test_news_publishers.py tests/07_researcher_community_forum/test_news_scheduler.py tests/07_researcher_community_forum/test_news_classification.py tests/07_researcher_community_forum/test_news_relevance.py tests/07_researcher_community_forum/test_news_compose.py -q
```

MySQL链路只接收明确隔离地址 NEWS_RELEVANCE_TEST_MYSQL_URL 与 NEWS_RELEVANCE_TEST_REDIS_URL，要求本机、全新 news_test_* 库（utf8mb4_0900_ai_ci）和空Redis；运行 test_news_relevance_mysql.py，测试自动调用 Go TestNews 专项。不得使用业务库或共享Redis。代码启用前必须在已确认目标完成候选表迁移。

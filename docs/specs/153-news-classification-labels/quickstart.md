# 验证与运行

2026-10-23 已完成自然周扩展、业务迁移、历史补标、部署及推送，最新状态见
[实际发布记录](deployment-20261023.md)。下文 2026-10-22 的“未部署”内容保留为当时验收边界。

## 本地验证结果（2026-10-22）

| 验证 | 结果及边界 |
|---|---|
| Python 采集、调度、分类专项 | 44 项通过，包含最后一次进程硬中断的收敛状态 |
| 独立 MySQL 8.4 + Redis + RQ | 迁移升级→降级→升级、三条/两条批次、续跑与 PDF 队列隔离通过；正式 papers 哨兵未改变 |
| Python→MySQL→Go | Go 读取 Python 分类、中文家族、子类均匹配；不是仅分别 Mock 的接口 |
| Go 资讯专项 | TestNews 全部通过；内容过期、失败、未分类均返回空标签 |
| 前端专项 | 3 文件、10 项通过，含综述、多家族、空值、折叠测量、详情和分页 |
| 生产构建 | TypeScript 与 Vite 通过；存在项目已有 3Dmol eval / chunk 大小提示 |
| 浏览器 | 1500/1024/736/390/320px 无页面横向溢出、无标题/作者裁切；三栏独立分页、17 家族详情和英文标签通过 |
| 真实模型 | deepseek-v4-pro 对 5 条已有标题摘要返回合法分类和理由，未写业务库；见下文 |
| Go 全套 | 有 1 项既有失败，已在未修改 HEAD 副本复现，不算本 Feature 回归 |

Go 既有失败为 TestApplyPaperEvidenceArchivesManualReasonInReviewTransaction，
paper_evidence_manual_test.go:30 的 DELETE FROM scientific_evidence_checks 预期未匹配。
本次未修改相关审核逻辑。全套不能宣称通过；本 Feature 的专项与跨语言验证通过。

前端测试使用项目 Conda 环境的 Node 22；系统 Node 的实验性 localStorage 行为曾导致测试环境失败，
改用项目运行时后相关用例通过。浏览器截图是明确的布局测试夹具，不能当作线上已完成分类的截图。

## 真实模型抽样

[完整输入、目录和结果](assets/real-model.json) 保存已有公开标题/摘要与来源链接。
读取了当前业务目录八类，未将种子列表硬编码为分类范围；业务库只读，模型输出只保存到验收文件。

- BKBO 电化学生长：实验；当前目录没有适用家族，因此留空。
- CeRh2As2 多轨道安德森模型：理论模型与机制；重费米子家族。
- 过渡金属氢化物超导预测：理论计算；氢基家族。
- 超导数字集成电路 overview/outlook：综述；家族为空。
- YBCO 热处理制备：实验；铜基家族。标题出现 method 没有误标为理论方法类。

这些结果和输入主要贡献一致，但只是五条抽样，不证明所有资讯的科学分类准确性。
未假称通读全文，未额外下载或补摘要。

另用四条明确标为合成测试的输入验证方法创新、综述多家族、产业新闻留空、
引言理论背景不覆盖本文实验贡献；真实模型输出均符合预设规则。
它们保存在同一文件的 synthetic_boundary_cases，不冒充真实论文或扩大全站准确性结论。

## 复现命令

使用 scripts.local_deploy.environment 为本仓库定位 Python 运行时；其 bin 目录也提供测试所需 Node 22。
不要输出 .env 或模型凭据。

~~~sh
DATABASE_URL=sqlite:// "$PYTHON" -m pytest tests/07_researcher_community_forum/test_news_collection.py tests/07_researcher_community_forum/test_news_scheduler.py tests/07_researcher_community_forum/test_news_classification.py -q
cd frontend
npm run test:upload-ui -- tests/07_researcher_community_forum/news-classification.test.tsx tests/07_researcher_community_forum/news-feed.test.tsx tests/03_data_search_and_database_discovery/news-page-layout.test.tsx
npm run build
~~~

MySQL 联调需要显式 NEWS_CLASSIFICATION_TEST_MYSQL_URL 和 NEWS_CLASSIFICATION_TEST_REDIS_URL，
只接受 localhost 的空 news_test_* 数据库与空 Redis 库。测试运行
tests/07_researcher_community_forum/test_news_classification_mysql.py，
并调用本地 Go 的 TestNewsFeedMySQLContract；可用 NEWS_TEST_GO_BINARY 指定 Go 位置。
测试保留隔离数据供浏览器串联，复跑必须另建空测试数据库/Redis 库，不清空已有数据。

浏览器脚本 tests/07_researcher_community_forum/news-classification-browser.mjs 使用 PLAYWRIGHT_MODULE、
CHROMIUM_PATH、FRONTEND_URL 和 NEWS_BROWSER_API；后者指向 TestNewsFeedBrowserPreview 启动的隔离 Go 服务。
先验证真实 Python/MySQL/Go 响应在 React 中显示，再用布局夹具检查长标题和多家族。
[浏览器断言](assets/browser-results.json)、[桌面](assets/labels-desktop.png)、
[移动端](assets/labels-mobile.png)、[英文](assets/labels-english.png)。

## 部署与运行边界

本次已交付迁移、分类调度与界面代码；没有应用业务数据库迁移，没有对现存 1121 条资讯批量回填，
没有重启业务进程或推送。此数量是本次只读抽样时的快照，不是固定规模。

目标部署应先备份并按授权应用迁移，再部署 Go/前端与 Python Worker/Scheduler。
现有迁移仍有两个分支头，本次接在 20261022_0147b 后；没有擅自合并另一头。
分类历史补齐在新调度器启动后自动分批运行。最多三次尝试，失败不会改变采集成功水位。
目录及标题摘要变化会自动重判；纯模型更换不重跑已完成内容，避免无需求的全量费用。
不得在运行新代码时降级删除分类表；回滚需协调服务版本与数据备份。

## 工程原则

分类服务负责判断及任务状态，Go 仅查询，前端仅呈现；复用已有 LLM、目录与枚举，
不增加人工编辑、筛选或全文解析。输入指纹和尝试 token 只解决明确的并发/超时问题，
不引入新的任务平台或正式科研审核状态。

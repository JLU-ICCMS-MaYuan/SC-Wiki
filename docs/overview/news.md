# 超导快讯与最新论文

## 功能说明
/news 页面展示自动发现的超导新闻、预印本和期刊文章，另保留人工快讯和诺贝尔奖里程碑。
自动内容统一标注“自动采集，未经本站审核”，并提供来源、原文链接、发表时间和采集时间。
自动发现不等于论文入库，不进入正式科研数据库、审核队列、知识图谱或 PDF 解析流程。

## 当前行为
- arXiv 使用 cond-mat.supr-con 分类 API，按更新时间分页；去除版本编号形成稳定身份，版本升级更新原条目。
- Crossref 使用最近至少 30 天的发表日期窗口，分别查询 superconductivity、superconducting、superconductor、Josephson，按索引顺序完成游标分页，公开列表仍按发表时间排序。期刊原始在线发表日期优先，保留日期精度；仅保存书目信息，不存 Crossref 摘要。APS/ACS/Nature/Science 使用正确的 DOI 注册前缀，NSR/CPL/CPB/Materials Today 使用 ISSN 并逐条校验范围，避免将期刊 DOI 片段误当出版社前缀。
- APS 的 PRL/PRB/PRX，Nature 的 Nature/Nature Physics/Nature Materials/Nature Communications，Science 的当期和提前发表，以及 Materials Today 已有官方 RSS 适配，和 Crossref 补充组合使用。RSS仅保存元数据与原文链接，不抓取全文；没有可用官方RSS的来源继续通过索引获取，不声称逐家官网完整抓取。
- OpenAlex 至少滚动回看 30 天内、主来源为期刊的 `article/review`，本地拒绝明确未发表、未接收及 Zenodo 仓储 DOI。题名可证明相关性；自动关键词/主题有置信度门槛，摘要命中还需超导学术上下文。可选 NEWS_OPENALEX_API_KEY 使用 Bearer 头；无Key且有后续页时保留首批结果并记 partial/openalex_key_required，不把第一页200当完整成功。匿名共享预算耗尽可能返回429。
- Phys.org 读取官方超导 RSS，保留原标题与原文链接，只展示订阅摘要，不抓文章全文。
- Google News RSS 用固定查询 `superconduct OR 超导` 发现公开索引的社会、产业、政策或股票资讯。它不保证覆盖未被搜索服务收录的网页或微信公众号内容。
- 相同 DOI 或规范化原文 URL 的条目在事务内合并，保留来源链接；两个已知不同 DOI 不因错误复用同一URL而合并，不按相似标题猜测。预印本补充信息不把已经发表的条目退回预印本；聚合索引笼统的 journal-article 类型也不覆盖出版商明确的新闻标识。
- 自动条目保留 `content_type`、发现/原文来源与相关性依据，但分栏按内容语义：Phys.org 科研报道、出版社新闻及社会/产业资讯进入新闻；arXiv等进入预印本；正式期刊条目进入期刊栏。已知 Nature新闻、APS Physics、ACS C&EN 和 Science新闻栏目按报道识别。旧 display_kind 不再决定分栏，计数、分页和公开返回使用同一语义，不需先批量改写历史记录。新期刊类型使用 journal_article，不以元数据冒称完成同行评审核验。
- 页面按发表时间倒序，以 News、Preprints、Articles 三列并列展示；每列固定请求所属类型且每页 5 条，三列独立维护页码和翻页状态。只有年/月的日期明确标注精度。
- 三栏默认只显示北京时间当前自然周（周一零点至下周一零点）。翻页保留周锚点，末页或本周为空时提供“历史更多”，按发表时间从新到旧展示其余已收录条目，并可返回本周。仅年/月或未知日期不推定属于本周，保留在历史入口；计数和分页由服务端同一条件约束。旧 API 无 period 参数时保持全量兼容。
- 公开页面不展示来源更新状态面板、采集告警、错误码、最后成功时间或订阅窗口说明；后台仍保存采集状态用于运行诊断。页面继续区分资讯加载中、暂无条目和请求失败，保留列表失败后的重试入口。
- GET /api/news 保持人工快讯数组契约；数据库错误返回 HTTP 500，不再伪装为空结果。

## 用户界面
- **品牌 Hero**：页面显示 `Superconduct Wiki / 超导维基`、吉林大学物理学院物质模拟方法与软件教育部重点实验室署名和平台能力简介；仅保留跳转 Explore（`/search`）的 `Start Exploring / 开始探索` 主按钮。
- **三列资讯流**：自动资讯分为 News、Preprints、Articles 三栏；桌面端三列并排、窄屏纵向排列，每栏最多显示 5 条并独立使用 `Previous`/`Next` 翻页。三栏保持等高，每个资讯槽位使用统一高度，分页控件固定在栏底部对齐。
- **简洁列表**：默认显示标题、作者、来源类型及自动研究分类标签，隐藏完整摘要避免占满屏幕。卡片按屏幕宽度统一保留足够槽位高度，家族标签超出一行时显示 `+N`，详情展开全部标签。
- **详情抽屉**：点击条目打开右侧抽屉。原文只呈现一个入口，优先使用安全的条目原文URL，主URL无效时取安全备用链接；后台多来源追溯保留，不重复展示同URL的不同角色。只有期刊条目显示“期刊”字段，新闻不因刊载来源而被称为期刊论文。原文能否直达仍受外站访问条件影响。
- **类型标签颜色**：新闻用浅蓝色（#e3f2fd），预印本用浅紫色（#f3e5f5），期刊论文用浅绿色（#e8f5e9），低饱和度视觉舒适。
- **交互反馈**：列表项悬停显示背景色变化和手型光标；点击关闭按钮或遮罩层关闭抽屉。
- **响应式设计**：抽屉在桌面端占 50% 宽度，移动端全屏显示。

## 工作流程
Python 采集进程负责外部访问、过滤、规范化和写表；Go 仅提供只读列表接口；前端读取持久化结果，不现场抓取。
独立 schedule 进程每分钟检查日任务，默认北京时间 08:00；停机后按成功水位补跑，失败一小时后重试。
Docker Compose 以 `news-scheduler` 运行该调度进程，并以 `news-worker` 专门消费 `scwiki-news` 队列；两者等待迁移成功和 Redis 健康后启动，容器重启时自动恢复。RQ Worker 在 Redis 短暂连接异常或空闲读超时后会重建连接继续消费。上传 Worker 不消费资讯队列。本地开发执行 `scripts/dev.sh start` 时也会默认启动这两个进程，日志和 PID 分别由 `scripts/dev.sh logs/status` 管理。
Redis 互斥锁防止并发采集。
macOS 的资讯 Worker 使用 RQ SpawnWorker，以新解释器执行任务，避免 fork 后系统网络库触发 Objective-C 崩溃；Linux 仍使用原 Worker。启动日志记录实际 Worker 类名。
任务最长 900 秒，单请求有限重试；失败不前移成功水位，不清空已有资讯。

期刊入口或后续页部分失败时，保留已经取得的有效记录，来源记为 partial，不推进 last_success_at；
partial 和 failed 均按一小时重试。401/403/429 和错误请求分别记录稳定错误码，日志不包含私有Key。

## 自动研究分类

全部自动资讯（含新闻和科研报道）可根据已有标题、摘要自动判断研究类型：实验、理论、综述，按主要贡献单选。
理论再单选计算类、方法类、理论模型与机制；材料家族从当前数据库目录和别名中多选，不能判断的维度留空。
综述可带材料家族；产业资讯不强行分类。页面说明“标签依据标题和摘要自动判断”，不代表全文阅读或正式审核。

分类不占用采集事务或 PDF 队列。调度器每分钟先安排采集，再向资讯队列追加一个最多三条的分类批次，
以当前服务器默认 LLM 生成结构化结果；按最近采集和首次发现时间优先扫描，已完成且输入未变的条目跳过。
历史条目在同一路径下分批补齐，无需新增进程。标题、摘要、目录或规则变化后重判；不自动创建家族。
每次调用前保存尝试计数，失败一小时后重试，最多三次；运行中断五分钟后可恢复，最后一次过期尝试收敛为失败。
写回核验内容、目录及尝试标识，过期任务不能覆盖新结果。API 仅返回当前标题摘要对应的已完成结果，失败和待分类维度为空。

实现入口为 [分类服务](../../backend/news/classification.py)、资讯调度、Go 资讯接口及
[标签组件](../../frontend/src/components/NewsClassificationLabels.tsx)。分类新增的两张表需要先迁移，
再配套发布服务；当前生产启用和补齐结果见下方发布记录。

2026-10-23 已在当前生产实例启用，迁移、1,357 条存量补标和自然周/历史入口经过公网验证；
本地副本 1,121 条也已补齐。这些数量是发布时快照，分类 completed 包括明确留空的维度。
发布镜像、数据不变性、真实验证和来源覆盖边界见 [发布记录](../specs/153-news-classification-labels/deployment-20261023.md)。

## 数据与约束
自动资讯使用 news_feed_items、news_feed_identities、news_feed_sources；分类另存 news_feed_classifications 和
news_feed_material_families。分类保存研究类型、理论子类、输入与目录指纹、规则版本、模型、理由和尝试状态，
家族关联只引用已有 material_families；资讯删除或合并时级联删除对应附属记录。无正式 papers/材料/物性表写入。
来源请求固定白名单端点，响应限 5 MiB；arXiv 请求间隔至少 3.1 秒，其他来源至少 1 秒。
科学元数据与 Phys.org 连接不继承系统代理，避免本地代理故障中断论文采集；Google News 连接保留系统代理，以适应受限网络。单个来源的连接失败仍只记录该来源失败。
通用来源首次回看默认 7 天，后续重叠 2 天；期刊发现与 OpenAlex 至少回看发表日期 30 天，并依靠身份键去重。期刊索引默认每查询最多 100 页，其有效部分与未完成状态分别保存，不伪装完整成功。
RSS 只能补回当前订阅窗口；已移除的历史内容无法保证找回。Crossref 标题筛选及 OpenAlex 的保守期刊/相关性规则会漏掉边界内容，不承诺覆盖全部超导论文。当前自动过滤只能阻止未来误收；规则收紧前写入的 Zenodo 历史条目由 [Issue #92](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/92) 通过独立、可审计的数据清理流程处理。
运行命令不会自动建表，生产迁移和进程部署仍需操作者明确执行。

## 代码与测试
- [采集适配](../../backend/news/sources.py)、[事务与去重](../../backend/news/service.py)、[日调度](../../backend/news/scheduler.py)、[命令入口](../../backend/news/__main__.py)。
- [数据模型](../../backend/news/models.py)、[#63 迁移](../../alembic/versions/20260831_0063_news_feed.py)、[#88 迁移](../../alembic/versions/20260903_0003_networked_news_discovery.py)。
- [Go 列表接口](../../goserver/handlers/news_feed.go)、[React 资讯组件](../../frontend/src/components/NewsFeed.tsx)。
- [Python 与页面测试](../../tests/07_researcher_community_forum/)、[Go 测试](../../goserver/handlers/news_feed_test.go)。
- [#88 完整运行与验证说明](../specs/88-networked-superconductivity-discovery/quickstart.md)、[Compose 部署修复](../specs/86-news-scheduler/quickstart.md)。

## 验证与运行边界
资讯与分类专项通过 Python 单元测试、隔离 MySQL 迁移/RQ 测试、Python 写入后 Go 读取的契约测试、Go 资讯测试、页面交互测试和前端生产构建。
在线 OpenAlex 30 天窗口只读验证确认目标 ACS DOI 的发现与原文来源映射，并拒绝 Zenodo DOI；此结果不表示生产运行环境已部署。
浏览器使用真实新闻处理器与隔离数据库检查桌面/手机布局；人工快讯响应在该预览中为测试样本。
本轮 Go 全包测试仍有论文证据审核测试 TestApplyPaperEvidenceArchivesManualReasonInReviewTransaction 的既有失败，已在未修改 HEAD 副本复现；未把定向资讯测试当作全包通过。

## 相关变更记录
[Feature #160](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/160) 更新内容分栏、单原文入口与期刊发现；[研究](../specs/160-news-source-semantics/research.md)和[验证记录](../specs/160-news-source-semantics/quickstart.md)区分代码实现、真实入口结果、外站访问限制与部署状态。
[Bug #157](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/157) 修复 macOS 资讯采集的 fork 崩溃，恢复本地采集及本周展示；[诊断与验收](../specs/157-macos-news-worker/spec.md)。来源网络失败与 Worker 恢复分开记录，不将空列表解释为没有相关文献。
[Feature #156](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/156) 移除公开资讯页的来源更新状态展示，保留条目来源信息与后台采集诊断；[规格](../specs/156-remove-news-source-status/spec.md)。
[Feature #153](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/153) 增加自动分类标签；
[专项验收](../specs/153-news-classification-labels/quickstart.md) 包含真实模型抽样、跨语言链路、浏览器检查及未部署边界。
[Feature #63](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/63) 与 [Spec](../specs/63-daily-superconductivity-news/spec.md)；[Feature #83](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/83) 完成 News 品牌与三列独立分页；[Bug #86](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/86) 补齐 Compose 中的 scheduler 和 worker；[Feature #88](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/88) 扩展联网发现与过滤；[Maintenance #92](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/92) 跟踪历史 Zenodo 误收清理。
未完成协作事项以该 Issue 为准；本页不维护第二套任务状态。

## 诺贝尔奖人物展陈

`/news` 的诺奖时间线已替换为11位获奖者的原照弧形展陈：白色背景、按显示宽度保留间隔、主位放大、侧位转斜，姓名与说明随人物移动。支持拖动改方向、悬停暂停、人物索引、键盘和减少动态；点击新标签页进入 `/nobel/:personId`。详情可直接打开和刷新，未知人物显示明确提示。

每张肖像的个人成果后列出同年度共同获奖者，单独获奖者单独说明；详情列明授奖份额及官方引用。特别区分1973年江崎的半导体隧穿、Giaever的超导体电子隧穿、Josephson的超电流理论预言，份额分别为1/4、1/4、1/2；共同获奖不等于合作完成同一成果。

界面与资料支持中英文，Demo和正式页面复用 `frontend/src/features/nobel/` 的组件、数据、布局和原照。图片随前端构建输出至 `/assets`；无新增业务数据库或API。当前仍为原照版本，最终漫画、图片外部许可与全面史实审校未完成。本地源码验证不代表云端部署，见 [#159接入验证](../specs/159-nobel-portrait-exhibition/integration-validation.md)。

诺奖展陈默认自动旋转，不显示操作说明或暂停开关；选择姓名索引后继续，悬停/键盘阅读及减少动态行为保留。展区高度按全部人物完整旋转周期的最大占用固定，横线、索引和联系区域不随旋转上下移动，临界位置保留约12px余量；索引下显示马原（mayuan@calypso.org.cn）、郭强（未提供邮箱，仅姓名）、钟鑫（zhongxin@jlu.edu.cn）、刘寒雨（hanyuliu@jlu.edu.cn）及联系邀请。参见[紧凑布局验证](../specs/159-nobel-portrait-exhibition/compact-validation.md)。

当前展陈按用户确认排除半导体隧穿获奖者江崎玲于奈，保留约瑟夫森及超流氦-3理论获奖者莱格特，总计11人（1+3+2+2+3）。江崎没有卡片、索引或人物详情；1973年的完整获奖历史仍在共享说明中准确列出其姓名及原始份额。展陈名单和完整奖项元数据分开维护。

窗口、字体、语言或内容重排时重新测量高度；短人物经过主位时允许必要空白，以保证横线位置稳定。见[固定分隔线验证](../specs/159-nobel-portrait-exhibition/fixed-divider-validation.md)。

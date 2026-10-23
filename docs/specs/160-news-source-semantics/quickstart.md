# 验证记录

## 2026-10-23 本地实现与隔离验证

- Python 资讯专项 68 项通过；覆盖官方RSS与索引、三类内容、期刊范围、在线发表日期、重复URL/DOI、无Key/有Key分页、部分完成保存与一小时重试、凭据不进入URL或日志。
- Go 资讯专项通过，包含旧 Phys.org、Nature新闻、Science新闻、APS Physics及ACS C&EN在计数/分页/返回中的一致分栏；读取没有改写历史行。
- 前端相关 13 项通过。另有1项旧“诺贝尔奖里程碑”断言因并行 #159 替换该页面而失败，已在未修改的 HEAD 副本复现；本任务没有修改该断言，定向验证显式排除此无关用例，不能声称整套测试全绿。
- 从已提交 HEAD 导出前端、仅覆盖本任务文件的 TypeScript/Vite 构建通过，没有混入谱线等其他任务的未提交改动；构建仍有既有 3Dmol eval/chunk大小提示。
- 隔离 SQLite 的真实 Go API 配合生产构建页面，确认旧 display_kind=journal_article 的 Phys.org 条目进入新闻，期刊栏只保留期刊测试条目；详情同URL不同角色只渲染一个原文入口。
- 对运行中的本地接口做只读检查，该条已返回 kind=news、display_kind=news；后台仍保留两份角色记录。本轮没有主动部署、重启服务、启动业务采集或执行历史批量改库。

[页面/API断言](assets/verification/results.json)、[三栏截图](assets/verification/columns.png)、[单入口截图](assets/verification/single-link.png)。页面是隔离夹具，不是线上已经完成新采集的证明。

## 真实来源只读验证

[完整样本](assets/verification/live-sources.json) 保存时间、状态、数量和少量原文链接。每个查询最多4页；只拉公开元数据，不写业务库，不配置或注册Key。

| 来源 | 本次查询状态 | 收录候选记录 / 唯一内容 |
|---|---|---|
| APS | 配置入口完成 | 161 / 149 |
| ACS | 配置查询完成 | 4 / 4 |
| Nature | 配置入口完成 | 25 / 22 |
| Science | 配置入口完成 | 3 / 2 |
| NSR | 配置查询完成，未命中 | 0 / 0 |
| CPL | 配置查询完成 | 2 / 2 |
| CPB | 配置查询完成 | 11 / 11 |
| Materials Today | 配置入口完成，未命中 | 0 / 0 |
| OpenAlex | 无Key，部分完成 | 99 / 99（读取100条候选） |

候选记录会有 RSS/API 对同一 DOI 的重复来源，写入时才合并；表内数量不等于数据库新增行数。
“完成”只指配置的查询/入口执行完成，不保证整个出版集团无遗漏，零命中也不是证明该期刊没有超导新论文。
例如 ACS 真实返回 2026-10-22 的 Resist-Free Shadow Deposition Using Silicon Trenches for Josephson Junctions in Superconducting Qubits，
DOI 10.1021/acs.nanolett.6c02734；Nature Physics官方RSS也返回10月20日至22日相关研究。
后续OpenAlex匿名请求返回共享IP日预算耗尽的429，此后停止探测，未更换出口绕过额度；上表是先前时刻的有效快照。

## 原文打开与待确认事项

Phys.org 原文URL初次普通HTTP探测200，后续自动化Chrome得到400或连接验证页；常规Chrome等待30秒仍未取得正文。
已确认两条原链接的URL完全相同、应用重复展示已修复，不能把“第一条地址失效”写成已证实根因，也不能宣布原文直达验证通过。
已向用户询问其普通浏览器结果，当前仍待答复；不通过复制外站正文或构造未经验证的替代地址伪装成功。

用户尚未选择这次采集写库/应用的目标环境。按 AGENTS.md 等待明确本地实时开发、本地 Docker、阿里云或本轮仅代码；不继承上一 Issue 的部署许可。
OpenAlex Key为可选的私有配置，有Key后完整真实分页仍需在目标环境验证；本次没有代注册或购买额度。

## 复现入口

Python：test_news_collection.py、test_news_publishers.py、test_news_scheduler.py、test_news_classification.py。
Go：go test ./handlers -run TestNews -count=1；隔离预览仅在 NEWS_SEMANTICS_PREVIEW_ADDRESS 显式设置时启动SQLite夹具。
前端：news-feed、news-classification、news-page-layout三个测试文件，测试模式排除已复现的旧诺奖断言。
源码与调用链均未引入新依赖或服务，生产期刊来源以 backend/news/publishers.py 为实际目录。

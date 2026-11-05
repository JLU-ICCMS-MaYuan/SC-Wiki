# 部署与本地接入验收

日期：2026-11-05（Asia/Shanghai）。**本地原生 SC-Wiki 已接上 4090，采用阿里云 HTTPS 中转。**

## 当前实际链路

本地 Vite 5173 → Go 8080 → Python 8000 → `https://www.sc-wiki.com/embedding/v1` → 阿里云 Caddy → 私有网桥 172.19.0.1:18080 → 4090 主动建立的受限 SSH 隧道 → GPU 上的 Qwen3-Embedding-4B。

阿里云只增加中转入口和专用隧道账号，其网站自身的模型配置、业务数据和向量索引未切换。本次没有构建或发布应用镜像。

## 真实结果与证据

| 验收 | 实际结果 | 依据 |
| --- | --- | --- |
| 外部 HTTPS | 18 项通过，正常验证证书；单条/批量、维度、鉴权、错误输入及相关性通过 | [外部接口](evidence/connection-https-smoke.json) |
| 全量重建 | 1072 条，ID、payload 逐条相等，源集合前后摘要一致 | [重建回执](evidence/connection-rebuild-receipt.json) |
| 原集合保留 | paper_chunks 仍为 1072 条，未更新、未删除 | [数据核验](evidence/connection-data-preservation.json) |
| 新主集合 | paper_chunks_qwen3_4b_20261105_v2，1536 维 | [配置与写入](evidence/connection-data-preservation.json) |
| 实际向量写入 | embed_and_index_chunks 经真实模型生成向量，在隔离临时 Qdrant 集合写入、重读后清理 | [实际写入](evidence/connection-data-preservation.json) |
| 网站同一接口链路 | Vite→Go→Python 的语义检索 HTTP 200，返回 10 条片段，关联已批准论文 1429 | [检索结果](evidence/connection-application-search.json) |
| 进程配置 | Python API、上传 Worker 均加载新模型、地址及集合；其他原停止角色未启动 | [白名单配置](evidence/connection-process-config.json) |
| 退出全部交互 SSH | 网站检索仍 HTTP 200，返回 10 条片段 | [退出后调用](evidence/connection-after-ssh-logout.json) |
| 隧道故障恢复 | 主动终止 relay 单元后，约 10.453 秒恢复真实 1536 维调用，重启计数为 1 | [恢复结果](evidence/connection-relay-recovery.json) |
| 网站及路径隔离 | 原首页、/health 为 200，/embedding/pooling、/embedding/tokenize 为 404 | [路径检查](evidence/connection-route-checks.json) |
| 代码回归 | RAG 单元目录 34 项通过 | [测试输出](evidence/connection-unit-tests.txt) |
| 制品与权限 | GPU 源码 629af7e0，Caddy、片段、SSH 限制配置均有 SHA256；root GatewayPorts 保持 no | [运行事实](evidence/connection-infrastructure.json) |

本次验证不代表整篇 PDF 科学字段解析或全库相关性评测通过。文字及字段提取继续使用既有程序、聊天模型；改变的是 Embedding 与检索向量。

## 真实失败及修复

1. 初次公网收到前端 HTML，发现 Caddy 单文件挂载实际指向 ea300d3 发布目录，而 current 已指向 e2560d1f-actions。修复实际绑定文件并重载；最终将规则放入独立持久卷，基础 Caddyfile 只保留可选 import。有/无片段两种配置均以实际 Caddy validate 验证，缺片段时保留原网站行为。
2. 首轮重建在第 70 条后收到 HTTP 400：已有片段为 13010 Token，超过初始 8192。固定模型 tokenizer 核查全量 1072 条后，运行上限改为 16384、并发序列 2、批 Token 上限 16384；BF16 与 0.65 显存利用率保持。不截断、不跳过、不放宽输出断言；超长拒绝回归使用新上限之外的文本。完整重建成功后，已清理 70 条记录的失败临时集合，原集合一直保留。
3. 公网诊断中曾出现个别 TCP 建连超时，后续相同入口的实际应用、SDK 和持久连接检查通过。保留既有有限重试，没有提高超时掩盖失败；未进行持续可用性压测。

见 [失败观测](evidence/connection-failures.json)、[tokenizer 核查](evidence/connection-token-audit.json)。含原文本、旧向量和旧配置的备份只在本机 `.local/embedding-backups/`，不进入 Git。

## 切换、回退与范围

切换前队列为空、Worker 空闲，仅停止并恢复本地原本运行的 Python 与上传 Worker。只修改六项 Embedding/主集合配置，其他配置字典核验一致，.env 和备份均为 0600。MySQL、Redis、Go、前端和其他角色保持。

回退时恢复原模型与集合设置，不覆盖后来无关配置。若切换后已有新增发布，需要先核对新增记录，不能把恢复旧设置当成所有新索引都已回退。主机开机自启仅检查配置，没有重启主机验收。

此前审核提示不能代表所有出站 SSH 不可用。本次单独执行标准嵌入转发命令成功，再使用受限专用公钥连接，没有伪造审核或包装被拒命令绕过权限。

## 历史与远程文档

[首次部署记录](initial-deployment-validation.md)保留初次成功、维度失败及修复；其中未接入状态只代表当时阶段。未获得 Git 推送授权，不为关闭 Issue 自动 push，远程文档可达性单独核查。

# 技术研究与决策

## 现状依据

- [现行独立 Embedding 配置](../../overview/05_Retrieval-Augmented_AI_Question_Answering/availability-and-configuration.md)：既有后端支持 OpenAI 兼容接口；模型或维度变化须重建索引。
- [#146](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/146) 为网站部署，不能将本次独立服务器部署当成该网站已更新。
- [官方模型卡](https://huggingface.co/Qwen/Qwen3-Embedding-4B)：2560 原生维度、Matryoshka、100 多种语言；推荐 query 指令，document 不加指令。

## 选择标准推理服务

采用 vLLM 0.11.2 的 pooling/embed 能力及标准 /v1/embeddings。使用显式 LAST pooling、归一化和 Matryoshka 配置，保留模型名，不将它命名为 text-embedding-v4。

选固定且支持 Qwen3 的发行版，而非在部署时无边界升级到最新版本。虚拟环境安装及 freeze 保留真实传递依赖。

## 下载与模型身份

HF 主站不可达时可使用 HF 镜像或 ModelScope 官方 Qwen 仓库传输。传输来源与模型身份分别记录；所有文件均验证固定 HF revision 清单：LFS 文件 SHA256、普通 Git 文件 blob SHA1；下载不同版本时拒绝启动，不凭同名认定相同权重。

## 网络与访问

初始监听 127.0.0.1:8000，配置密钥，通过现有 SSH 网关测试转发。不以随机公网隧道代替长期入口，不擅自修改平台映射。SSH 不支持转发时，保留服务并明确外部访问缺项。

## 输入语义与集成边界

调用者负责 query 的英文任务指令，document 直接编码；标准 OpenAI 接口无额外 text_type 假设。冒烟验证用相同固定指令。未来接入 SC-Wiki 时再处理查询角色，并重建文献索引；本次不修改其调用逻辑。

## 未采用方案

- Docker/TEI：目标未安装 Docker，本次原生环境即可满足，不增加全局容器运行时。
- 自写 FastAPI 推理服务：标准引擎已满足接口，无需另写批调度与鉴权。
- 直接更改网站模型名：新旧向量空间不同，不符合现有索引约束。

## 实际安装与传输调整

Ubuntu 未安装 ensurepip。先创建不带 pip 的独立虚拟环境，再使用 PyPA 官方 get-pip.py 引导 pip，没有安装全局软件包。串行下载 CUDA 大文件较慢，保留已下载 wheel，改用经 PyPI SHA256 核对的 uv 0.9.10 和镜像并发安装；vLLM 仍固定 0.11.2，最终以 freeze、pip check 和真实 GPU 验收为准。

模型下载保留已完成前缀，通过 ModelScope HTTP Range 并行传输剩余部分，拼装后仍按固定 HF 清单核对最终 SHA256。传输加速不改变 revision 或放宽哈希条件，成功后清理临时分片。

## 阿里云入口早期核查（历史）

用户提供连接信息并授权检查阿里云，凭据独立保管，不归档。实际核查到：SSH 允许 TCP 转发，GatewayPorts 默认 no；Caddy 2.10.2 在现有 80/443 提供 HTTPS，scwiki_internal 网桥网关为 172.19.0.1，网站健康返回 200。

拟由 4090 主动建立受限反向隧道，仅监听阿里云 Docker 私有网桥的 18080；Caddy 只增加 `/embedding/v1/embeddings` 和 `/embedding/v1/models` 两个入口，vLLM 仍只监听 GPU 回环地址。无需算力平台开放入站端口，也不开放阿里云新的公网端口。

`aliyun-Caddyfile.proposed` 已用实际 Caddy 版本校验；`relay-sshd.conf.proposed` 已通过 sshd -t 和指定用户有效配置检查，root 等既有用户仍 GatewayPorts=no。只是配置校验，没有启用。

GPU 出站 SSH 测试触发算力平台“工单命令执行复核”，尚未执行。不得通过重新包装命令、后台启动等方式绕过审核。阿里云入口变更另已向用户提出授权请求，未取得答复及平台放行前不实施依赖变更。

本次等待最后已取消，未执行该出站 SSH 命令。用户随后只询问本地直连与阿里云中转的区别，没有授权阿里云配置变更；中转保持备选。

## 输出维度边界修复

真实接口复现了 vLLM 0.11.2 在仅设置 is_matryoshka=true 时未校验维度上界的问题。通过引擎原生 matryoshka_dimensions 配置全部官方支持的 32–2560 维范围，恢复已定义接口约束；原始失败与修复后的 GPU 回归分别保留，不改变模型权重或隐藏失败。

## 最新接入结论与落地

用户明确“开始接上”后，标准单条 SSH 到模型端口实际成功，因此不再以先前命令审核提示认定整个出站通道不可用。专用账号、HTTPS 持久片段、本地配置和新集合切换已完成。此前“未授权/未接入”仅为早期讨论状态。

首轮重建遇到 13010 Token 的真实片段，固定 tokenizer 全量验证后按实际需要设置 16384 上限、并发 2，不截断科学文献。旧集合只读，1072 条数据在新集合完整重建；ID/payload 对比及源摘要验证通过，失败的 70 条临时集合已清理。

Caddy 单文件挂载与 current 符号链接存在真实差异，已修复实际绑定；最终采用基础文件可选 import 与独立持久片段，避免复制整份路由。默认无片段配置同样通过校验。仍需在后续发布中保留导入行和配置卷。

实际前端入口检索、真实嵌入写入重读、退出交互 SSH 后检索及隧道故障自动恢复均已通过。公网诊断曾出现个别 TCP 连接超时，保留观测，不通过扩大超时隐藏问题，也不将短期通过写成持续可用性压测通过。

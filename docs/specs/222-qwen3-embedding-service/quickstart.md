# 使用与运维

**当前本地 SC-Wiki 已使用 4090 的 Qwen3-Embedding-4B，无需用户再手动填写连接配置。**

## 当前配置与数据

- 本地 Base URL：`https://www.sc-wiki.com/embedding/v1`。
- 模型名：`Qwen/Qwen3-Embedding-4B`；本地输出维度：1536；原生支持 2560 维。
- 主集合：`paper_chunks_qwen3_4b_20261105_v2`，1072 条。
- 原集合：`paper_chunks`，1072 条，保留未改；旧向量不能与新模型查询混用。
- 私有备份：本机 `.local/embedding-backups/20261105-qwen3-4b-v2/`，包含 source.jsonl、env.before、receipt.json，权限限制为本用户读取。
- 运行源码：GPU 模型启动器来自 `629af7e0b9709c69cbfcc29d5db913ce3925ac86`；vLLM 0.11.2、PyTorch 2.9.0+cu128；完整依赖见[冻结清单](evidence/dependencies.freeze.txt)。

本地到阿里云为 HTTPS，阿里云到 GPU 为 SSH 加密通道，访问需要独立模型密钥。阿里云站点自身的模型和索引仍未切换。

## GPU 服务与隧道

登录 GPU 后执行：

```bash
systemctl --user status qwen3-embedding embedding-relay
systemctl --user restart qwen3-embedding
systemctl --user restart embedding-relay
journalctl --user -u qwen3-embedding -u embedding-relay -n 60 --no-pager
```

根目录 `/home/singeuser/qwen3-embedding`，模型仅监听 `127.0.0.1:8000`。API 密钥位于该目录 api-key/config.env，权限 0600；SSH 私钥 relay_ed25519 也仅由本用户读取。不要把真实密钥提交 Git 或写入命令行。

当前 BF16、16384 Token、2 个并发序列、0.65 显存利用率。全量已有片段最大 13010 Token；超限拒绝，不截断原文。后台、自启配置、异常恢复及退出 SSH 后运行均验证；没有执行主机重启验收。

## 阿里云入口

专用账号 embedding-relay 只允许远端监听 `172.19.0.1:18080`，不允许交互 shell、密码登录或本地转发；root 原 GatewayPorts=no 保持。当前不开放新的公网端口，复用 443。

Caddy 基础配置为 `docker/Caddyfile`，通过可选 import 读取 `/config/embedding/*.caddy`。当前片段保存在 Docker 持久配置卷 `/var/lib/docker/volumes/scwiki-home_caddy-config/_data/embedding/embedding-gateway.caddy`；部署材料为 `scripts/embedding/embedding-gateway.caddy`。后续网站发布需保留这条 import 和配置卷。

原文件及 SSH 配置备份在阿里云 `/home/mayuan/sc-wiki/embedding-gateway/backups/`。现有 Caddy 单文件挂载实际对应 `releases/ea300d3/docker/Caddyfile`，current 对应 e2560d1f-actions；本次两处均已更新。后续更新不能只看 current 字符串，需核对容器实际读取的文件和哈希。

## 本地验证

在项目根目录使用当前 sc-wiki Python 环境：

```python
from backend.ingest.embedder import embed_texts

query_vector = embed_texts(["高压富氢材料的超导临界温度"], purpose="query")[0]
print(len(query_vector))  # 1536
```

查询使用 `EMBEDDING_QUERY_INSTRUCTION`，文献正文保持原文。没有配置该指令的其他供应商继续原请求行为。已有逻辑 paper_chunks 查询会解析到当前配置的新物理集合。

## 更新、重建与回退

新版本先验证权重、依赖和源码身份；索引切换使用 `scripts/embedding/rebuild_collection.py` 新建尚不存在的独立集合。工具私有导出旧记录和向量，逐条核验 ID/payload、目标向量及源数据摘要，失败不修改原集合或应用配置。

当前仅重启了本地原已运行的 Python 和上传 Worker。变更模型或集合后须确保所有实际消费者加载相同设置，不能混用旧进程。

回退时先核对切换后有无新发布，仅恢复备份中六项 Embedding/集合设置，不覆盖后来其他配置，恢复必要角色。保留的新旧集合不删除；如需停止模型，执行 `systemctl --user stop qwen3-embedding`，不会删除论文或草稿。

真实结果见[接入验收](validation.md)。PDF 字段提取仍走既有解析程序和聊天模型；生成检索向量、问答检索时才使用这里的嵌入模型。

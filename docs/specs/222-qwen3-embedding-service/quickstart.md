# 使用与运维

服务器内服务已部署并通过真实推理、重启、异常恢复及退出 SSH 后常驻验证。外部入口尚未交付，本地应用目前不能直接使用下方回环地址。

## 实例与身份

- 主机：`gpu-single4090`；系统用户：`singeuser`。
- 运行方式：用户独立 Python 虚拟环境与 systemd 用户服务。
- 根目录：`/home/singeuser/qwen3-embedding`。
- 模型：`Qwen/Qwen3-Embedding-4B`，固定 revision 见 `scripts/embedding/model-manifest.json`。
- 实际运行源码：`4d00dfbc4fe529695d1c9b1742078774b2a05e0e`；vLLM 0.11.2、PyTorch 2.9.0+cu128。完整依赖见 [冻结清单](evidence/dependencies.freeze.txt)。
- 服务地址：机器内 `http://127.0.0.1:8000/v1`；当前不代表外部地址。
- 密钥文件：服务器根目录下 `api-key`；配置文件 `config.env`，均为 0600，真实内容不写入仓库。

## 登录与启停

使用用户已提供的 SSH 网关登录；密码独立保管，不写入文档。

```bash
ssh -p 10086 -l 'singeuser@singeuser@gsinge' 'cloud.mzq.cn'
systemctl --user status qwen3-embedding
systemctl --user start qwen3-embedding
systemctl --user restart qwen3-embedding
systemctl --user stop qwen3-embedding
journalctl --user -u qwen3-embedding -n 80 --no-pager
```

用户 linger 已开启，服务已配置 enable，退出 SSH 后运行与异常恢复均已验证；未执行主机重启。完整边界见 [验证记录](validation.md)。

## 机器内验证

```bash
set -a
. "/home/singeuser/qwen3-embedding/config.env"
set +a
"/home/singeuser/qwen3-embedding/.venv/bin/python" "/home/singeuser/qwen3-embedding/source/smoke.py"
```

SDK 调用示例：

```python
import os
from openai import OpenAI

client = OpenAI(base_url="http://127.0.0.1:8000/v1", api_key=os.environ["VLLM_API_KEY"])
result = client.embeddings.create(
    model="Qwen/Qwen3-Embedding-4B",
    input=["Hydrogen-rich materials may exhibit high-temperature superconductivity."],
    dimensions=1536,
    encoding_format="float",
)
print(len(result.data[0].embedding))
```

原生输出 2560 维，指定 dimensions=1536 时缩短并重新归一化。
允许范围为 32–2560 维；越界请求被拒绝，不会静默返回不同长度。
检索问题添加 `Instruct: Given a research paper query, retrieve relevant scientific passages that answer the query` 与换行后的 `Query: <问题>`；文献直接编码。

## 外部访问边界

2026-11-05 实测平台 SSH 网关拒绝普通 TCP 转发，返回 `administratively prohibited: port forwarding is disabled`。
因此 `ssh -L` 当前不可用，不能将本地创建的监听端口当成已通的隧道。
需要平台提供端口映射、固定服务地址或内网/VPN 接入；已向用户询问具体条件。
当前服务仅回环监听，不因转发失败自动开放公网或建立随机第三方隧道。

## 更新与回退

1. 核对新源码提交、模型清单与依赖，不覆盖未核验权重。
2. 保留旧环境、模型身份和私有配置；先离线验证新制品，再停止本次服务切换。
3. 使用新源码更新本服务，重新执行 smoke 并记录 GPU、依赖及源码身份。
4. 回退时停止本次服务、恢复旧部署材料后重启；临时停用可执行 `systemctl --user disable --now qwen3-embedding`。

本服务不持有业务论文或索引，停止不会删除 SC-Wiki 数据。启停只影响本次模型服务。

## SC-Wiki 接入边界

本次没有修改网站配置和旧向量索引。接入前需确认实际消费实例的网络、查询指令、模型与维度，并以新模型重建文献索引；不能把现有 v4 向量与新模型向量混用。

## 阿里云入口备选检查

已登录用户指定阿里云实例做只读核查；现有 HTTPS、SSH 转发及 Docker 网桥具备设计条件。候选 Base URL 为 `https://www.sc-wiki.com/embedding/v1`，目前未启用，不能按已可用地址调用。

4090 出站 SSH 测试需要算力平台工单复核，本次等待已取消且未执行该命令。先由平台放行通道，再在获得用户授权后设置阿里云专用隧道账号与 Caddy 入口，不能重新包装命令绕过审核。

草案位于 `scripts/embedding/aliyun-Caddyfile.proposed`、`relay-sshd.conf.proposed`、`embedding-relay.service.proposed`；仅配置校验已经通过，不代表端到端连接通过。

本地不必须经阿里云。平台若提供固定 HTTPS 映射或 VPN，本地和未来阿里云均可直接访问 GPU；当前仅有 SSH 登录能力不等于模型端口开放。用户正在讨论直连与中转，尚未授权阿里云配置变更。

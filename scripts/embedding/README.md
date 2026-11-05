# 独立 Qwen3-Embedding-4B 服务

此目录为 [#222](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/222) 的部署材料，
与 SC-Wiki 网站进程、数据库、旧向量索引独立。

## 材料

- `requirements.txt` 固定 vLLM 版本；在目标独立虚拟环境安装，安装后另存完整 freeze。
- `model-manifest.json` 固定 HF revision 和各文件 Git/LFS 身份。
- `download_model.py <模型目录>` 下载并校验；`--verify-only` 离线复核全部文件。
  默认通过 ModelScope 传输权重、HF 镜像传输固定版本的小文件，均按 HF 清单验证。
- `serve.py` 先校验模型，再使用标准 vLLM 提供回环地址 `127.0.0.1:8000`。
- `qwen3-embedding.service` 为用户级 systemd 模板。
- `smoke.py` 对真实 HTTP 服务验证鉴权、模型身份、批次对应、维度、范数、异常与跨语言冒烟。

## 凭据与运行

私有 `config.env` 必须设置 `VLLM_API_KEY`（至少 32 字符），并限制权限为 0600。
不要通过命令行传密钥，不提交真实凭据。不安装模型服务到全局 Python。

当前参数：BF16、16384 Token、2 个并发序列、0.65 显存利用率，禁用请求与访问日志。
调用模型名固定为 `Qwen/Qwen3-Embedding-4B`，原生输出 2560 维，可请求 1536 维。
引擎原生配置限定官方 32–2560 维范围，越界请求会被拒绝。
检索问题由调用者添加模型卡推荐的任务指令；文献正文直接编码。

详细部署、启停及访问方式见 [#222 运维说明](../../docs/specs/222-qwen3-embedding-service/quickstart.md)。
运行状态及性能以 [真实验证记录](../../docs/specs/222-qwen3-embedding-service/validation.md) 为准。

当前本地 SC-Wiki 已通过阿里云 HTTPS 入口使用该模型。`embedding-gateway.caddy`
放在 Caddy 持久配置卷中，项目 `docker/Caddyfile` 通过可选 import 导入；没有片段时保留原网站行为。
历史 `.proposed` 文件保留完整配置和服务模板供对照，不作为“尚未启用”的状态来源。

`rebuild_collection.py` 使用独立新集合和私有备份，核验 ID、payload、向量及源摘要，不修改原集合。
当前已重建 1072 条并切换本地主集合，实际版本、范围和回退路径见运维说明。

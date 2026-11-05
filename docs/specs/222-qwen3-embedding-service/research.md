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

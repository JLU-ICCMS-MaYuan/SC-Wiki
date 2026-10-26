# 主站预测契约

入口为 `/tc-predict`，可选查询参数 `group=ambient|hydride`；主站侧栏负责分类，URL 支持刷新和返回。已选择模型的临时输入／结果在当前页面实例内，不写数据库。模型目录只有四个已启用模型；暂停的 SISSO 81 不在主站目录或下载白名单。

- `GET /api/tc-models/catalog`：正式模型目录与数据可用状态、来源和下载地址。
- `GET /api/tc-models/health`：预测模块存活、解释器存在状态和权重数量；不是完整科学就绪证明。
- `GET|HEAD /api/tc-models/datasets/{id}`：只允许目录中的固定文件，校验摘要后返回附件；未知 ID 404，缺失或不匹配 503。
- `GET /api/tc-models/examples/{id}`：作者公开 CIF 示例，仅 nb／pb／al。
- `POST /api/tc-models/predict`：复用已验收结构／参数输入，JSON 最大 300 KiB，结构最大 256 KiB；无效输入 400，第二个同时结构请求 429，缺环境／制品或运行故障 503，结构超时 504。
- `POST /api/tc-predict/`：原 multipart 文件接口保留，前端同页展示原模型结果。

BETE 在固定服务端解释器中执行 `backend.prediction.worker`，通过标准输入接收 JSON、标准输出返回结果；请求不可指定命令、文件路径或远程 URL。主进程只加载目录和轻量公式，不导入旧 e3nn／PyG。当前本地单 Uvicorn 进程的结构并发上限为 1；多进程／多机调度不在本次范围。

API 调用链为 Vite 5173 → Go 8080 → FastAPI 8000，没有 Demo 端口代理。基础环境不足时已有参数模型和其他站点 API 不应跟随失效；协程取消及超时会清理本次派生进程。

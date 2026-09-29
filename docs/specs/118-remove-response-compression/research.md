# 技术调研：移除应用层双重响应压缩

关联 [Spec](spec.md)、[Plan](plan.md)。

## 故障定位

- 决策：判定为传输编码故障，而非解析数据故障。
- 证据：
  - 任务 `6aab86f4…` 状态为 `ready`，38/38 分段完成；Redis state/draft、`review_artifacts` 下 manifest、全部分段结果与 `result.json` 均为合法 JSON，不含 NaN/Infinity。
  - 网关日志中 `/parsing` 每 2 秒返回 200，与前端解析异常后 2000ms 重试分支一致。
  - `/api/form-definitions`（约 10KB）实测：8000 返回 1 层 gzip；8080 返回两个 `Content-Encoding: gzip` 头、2 层 gzip；5173 合并为 `gzip, gzip`、2 层 gzip。按头部声明解码后仍残留 gzip 字节，JSON 解析失败。
- 限制：`/parsing` 需登录，未直接抓取该接口响应；结论由同链路公开接口推定。

## 压缩来源

| 位置 | 引入提交 | 当时理由 |
| --- | --- | --- |
| `backend/main.py` `GZipMiddleware(minimum_size=1000)` | `70d8187`（2026-05-15） | Alexandria 大 JSON 响应；当时尚无 Go 网关 |
| `goserver/main.go` `gzipMiddleware` | `6bb4323`（2026-07-31） | 前端性能优化顺带加入，无 Issue |
| `docker/nginx.conf` 两处 `Accept-Encoding ""` | `e8eb6a6`（#19） | 绕开上传响应截断 |

Go 中间件对所有请求生效，包括 `NoRoute` 反向代理，且不判断上游是否已编码。

## 决策：两层压缩全部删除

- 理由：本地与内网部署带宽不是瓶颈；删除后无需任何条件判断，代码最少；nginx 绕过随之失去意义。
- 备选：
  - Go 跳过已编码上游：保留一层压缩，但仍需维护判断逻辑与测试。用户选择不保留。
  - 仅删 Python 层：Go 仍压缩，保留一处中间件。用户选择不保留。
  - nginx 统一压缩：本地 Vite 链路不经 nginx，两条链路再次出现差异。

## 受影响测试

- `goserver/main_test.go` 的 `TestGzipMiddlewareDropsLateContentLength` 只验证压缩中间件，随中间件删除。
- `goserver/handlers/paper_evidence_mysql_test.go` 中 `req.Header.Del("Accept-Encoding")` 是为避免 Go HTTP 客户端透明解压带来的差异，删除压缩后该行无作用，一并删除。
- `tests/01_decentralized_uploading/test_issue18_upload_limits.py` 只断言 `client_max_body_size`，不受影响。

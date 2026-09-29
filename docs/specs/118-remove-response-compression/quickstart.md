# 验证说明：移除应用层双重响应压缩

关联 [Spec](spec.md)、[Tasks](tasks.md) 与 [Issue #118](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/118)。

## 前置条件

本地服务已通过 `make start` 运行；在项目根目录执行。

## 重启受影响服务

```bash
bash "scripts/dev.sh" restart python
bash "scripts/dev.sh" restart goserver
```

## 三入口响应编码

`/api/form-definitions` 为公开接口，正文约 10KB，大于原压缩阈值。

```bash
for port in 8000 8080 5173; do
  curl -s -o /dev/null -D - -H "Accept-Encoding: gzip, deflate, br" \
    "http://127.0.0.1:$port/api/form-definitions" | grep -ic '^content-encoding' || true
  curl -s -H "Accept-Encoding: gzip" "http://127.0.0.1:$port/api/form-definitions" \
    | python3 -c "import json,sys; json.load(sys.stdin); print('JSON OK')"
done
```

预期：每个端口的 `Content-Encoding` 计数为 0，并输出 `JSON OK`。

## 解析详情

在浏览器（含 Safari）中打开上传页，展开 `2014 H3S-段德芳.pdf` 的解析详情，预期显示分段与汇总内容，
不再出现 `The string did not match the expected pattern.`。该接口需登录，凭据不写入文档。

## 残留检索

```bash
rg -n -i "gzip|Accept-Encoding|Content-Encoding" backend/main.py goserver docker/nginx.conf
```

预期无输出。

## 验证记录（2026-09-29）

| 检查 | 结果 |
| --- | --- |
| 8000 / 8080 / 5173 `/api/form-definitions`（10212 字节） | 均无 `Content-Encoding`，JSON 可解析；修复前 8080、5173 为 2 层 gzip |
| 8000 / 8080 `/openapi.json`（73429 字节） | 均无 `Content-Encoding`，JSON 可解析 |
| `2014 H3S-段德芳.pdf` 解析详情响应体 | 202329 字节，JSON 可解析，`ready`，38 个分段 |
| 残留检索 | 无输出 |
| 浏览器打开解析详情 | 用户确认 pattern 报错消失，5 步处理进度正常显示；草稿区 500 源自 Mac 环境缺少 greenlet，另行跟踪 |

5173 不代理 `/openapi.json`（仅代理 `/api`），该路径返回前端页面，不属于本次检查项。

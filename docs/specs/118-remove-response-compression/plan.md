# 实施计划：移除应用层双重响应压缩

**GitHub Issue**：[#118](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/118)

**日期**：2026-09-29

**Spec**：[spec.md](spec.md)

## 摘要

删除 Python `GZipMiddleware` 与 Go `gzipMiddleware`，删除 nginx 中为绕开压缩而清空的
`Accept-Encoding`，并清理对应测试与文档。不新增任何替代机制。决策依据见 [Research](research.md)。

## 技术上下文

- **语言与版本**：Python 3.12 + FastAPI 0.140；Go 1.25 + Gin 1.12
- **主要依赖**：Starlette 中间件栈；Gin 中间件与 `httputil.ReverseProxy`
- **数据存储**：不适用
- **测试体系**：`scripts/run-tests.sh go`；`pytest` 定向用例；curl 三入口实测
- **目标平台**：macOS 原生本地开发；Docker 生产链路（nginx → Go → Python）
- **约束**：不修改业务 API 与数据；不引入新依赖

## 质量门

| 约束来源 | 强制要求 | 设计如何满足 | 状态 |
|----------|----------|--------------|------|
| 用户确认 | 两层都删、不保留兼容 | 删除全部压缩代码与绕过配置 | 通过 |
| AGENTS.md KISS/YAGNI | 不引入额外机制 | 纯删除，无新增逻辑 | 通过 |
| FR-004 | 其余测试不失效 | Go 全包与相关 Python 测试回归 | 通过 |

## 源代码结构

```text
backend/main.py                                   # 删除 GZipMiddleware 导入与注册
goserver/main.go                                  # 删除 gzipMiddleware、gzipWriter 及注册
goserver/main_test.go                             # 删除压缩中间件测试
goserver/handlers/paper_evidence_mysql_test.go    # 删除无作用的 Accept-Encoding 清除
docker/nginx.conf                                 # 删除两处 Accept-Encoding "" 与压缩注释
docs/overview/02_Decentralized_Maintenance_and_Verification/deployment-and-runtime.md
docs/local-dev.md
```

**结构选择**：压缩只存在于两个中间件注册点，删除注册与实现即可；代理和业务处理器不变。

## 需求到设计的映射

| 来源 | 设计组件/接口 | 验证方式 |
|------|---------------|----------|
| FR-001 / US1 | `backend/main.py` 中间件栈 | 8000 入口 curl 无 `Content-Encoding` |
| FR-002 / US1 | `goserver/main.go` 中间件栈 | 8080、5173 入口 curl 无 `Content-Encoding`；解析详情接口返回 JSON |
| FR-003 / US2 | `docker/nginx.conf` | 检索无 `Accept-Encoding` |
| FR-004 | Go/Python 测试 | `run-tests.sh go`、定向 pytest |
| FR-005 / US2 | Overview、local-dev、Spec | 检索无差异项；链接检查 |

## 阶段与依赖

1. 删除 Python 与 Go 压缩及其测试（T001–T003），重启服务。
2. 三入口实测与解析详情验证（T004）。
3. 删除 nginx 绕过配置与文档差异项（T005–T006），全量检索与测试回归（T007）。

# 检索与代理契约

## 保留接口

`POST /api/papers/search/records`：JSON 请求包含 `elements`、`mode`、可选 `formula`、已收紧的筛选以及 `limit`、`offset`。

- 模式：`elements_combination_search`、`elements_exact_search`、`elements_contained_search`、`formula_search`。
- 前端默认 `limit=50`；分页使用响应 `total` 计算页数。
- 响应：`items`、`total`；每条记录保留 `record_id`、`paper_id`、年份、化学式、类型、压强、Tc、空间群、来源、状态和 DOI。
- 公开数据仅已批准论文；无匹配返回空列表，解析错误保持既有 400。
- `GET /api/papers/:id` 返回论文与材料状态下物性和结构；权限与不存在处理保持既有约束。

## 取消接口

- `POST /api/alexandria/search`
- `POST /api/htsc2025/search`
- `POST /api/papers/search/all`
- 原前端详情/下载路径 `/api/alexandria/material/*`、`/api/htsc2025/detail/*` 不再有调用入口。

不重定向为本地查询，不提供新响应适配或墓碑 Handler。未匹配路径沿用 Go → Python 通用代理；正常 Python 不提供这三个 POST 接口，因此返回 404/405。代理不可用时仍可能返回既有网关错误，不能声称任何环境均固定 404。

## 测试替身契约

已有上传和批准操作先请求 `/api/rag/evidence/preflight`。普通成功替身返回 `version`、`needs_check=false`、`records=[]`、`sources=[]`；最终操作仍需要 `expected_evidence_version`。

旧提交错误测试必须让预检成功，再在最终提交端点返回目标异常；审批断言按最终 `/review` 路径选取请求，不能把第一条 POST 当审批。共享证据组件的失败、取消、疑点等实际行为由原专项测试继续覆盖。

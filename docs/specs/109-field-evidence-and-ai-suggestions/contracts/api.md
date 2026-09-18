# 字段来源接口

沿用 `/api/rag/evidence` 及现有上传草稿、科学保存和 Go 审核接口。

- `POST /preflight`：返回全部可浏览核对项，包括 `required=false` 的空字段。`needs_check` 仅针对需核对的当前断言。只读，不调用模型。
- `POST /jobs`：增加 `purpose`，默认既有 `check`；`review_all` 仅用于管理员论文审核，清空本次跳过缓存并把已有判断、建议和证据送入复核。保留指定重试、进度、取消与版本验证。
- 上传解析内部生成使用 `generate` 目的，不增加用户点击；建议持久化后页面读取同一结果契约。
- `proposal`：沿用 `values/evidences/supported`，增加 `basis_kind/explanation`；所有引句都服务端复核，推断与推测不得声称直接支持。
- `POST /proposals`、`prepare`、`finalize`：允许上传者明确采用有效推断/推测，保存原来源类别；提交时应用，最终内容必须与准备值完全一致。管理员处理未获直接支持的采用值需理由。
- 上传提交：允许与服务端有效采用记录匹配的通用推测进入待审，不授予 `human_confirmed`。
- `POST /prepare-review`：通用推测必须由服务端已保存、匹配当前版本的管理员逐项决定放行。Go 二次校验并持久化全部字段来源/建议；可选空项不作为有效断言批准。
- 失效、越权和保存失败沿用既有错误。迟到任务不得覆盖更晚的人工输入或批准结果。RAG 输出保留采用依据限定。

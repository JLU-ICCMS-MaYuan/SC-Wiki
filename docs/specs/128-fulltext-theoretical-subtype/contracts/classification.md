# 全文理论子类型契约

## 输入、输出与所有权

- 现有上传任务的解析输入为主文和补充材料的解析文本；仅 `paper.paper_type=theoretical` 调用专门分类。参考文献不作为本文贡献。
- 草稿的 `paper.theoretical_subtype` 仍为 `calculation|method|theory|null`。服务端返回只读 `theoretical_subtype_assessment`，包含 `completed|uncertain|failed`、候选值、简短理由、1–3 条可定位引句、来源摘要、模型、规则版本及批次覆盖数；页码可能由来源解析提供。
- 引句保留文件 ID、片段序号和逐字文本；核对时按当前来源重新定位，不能仅信任客户端带来的位置。
- 现有 `PUT /upload-tasks/{task_id}/draft` 只接受人工编辑的当前分类值；请求中的分析对象不会替换服务端保存的分析。返修草稿也丢弃客户端回传的该对象。
- 本功能不新增公开分类、提交或审核路由。定向重跑只通过本地 CLI，以任务 ID 和预期文件名双重定位，且仅处理 `ready` 的理论论文草稿。

## 来源核对与兼容性

- 沿用字段路径 `paper.theoretical_subtype`。分析候选与当前值一致、引句可定位且有非 Methods 的贡献片段时，有效归纳可为 `source_kind=paper_synthesis`、`status=supported`；理由不能说成原文逐字写出的枚举。
- 用户改值、来源或规则变化后旧分析失效，只使本字段旧核对过期。旧草稿没有本次分析时，旧 `supported` 不自动转成新归纳资格。
- 提交时沿用已有 `ScientificEvidenceCheck` 和 `ScientificEvidenceSource`；文件 ID 与内嵌引句随正式论文重新定位，不新增正式业务列。

## 错误、权限与版本

- 没有可读取正文或没有可靠支撑时返回空值及 `uncertain` 原因；模型异常返回空值及 `failed` 原因，草稿仍可编辑。定向重跑期间任务状态或来源变化时停止写入旧结果。
- 上传草稿读写沿用当前任务所有者鉴权和既有提交校验；客户端不能凭请求对象制造分析或 `supported` 资格。本地 CLI 不对外暴露 API，不自动提交或批准。
- 分类规则版本与来源摘要进入本字段来源身份；提交后的正式来源还以论文内容版本和记录身份校验。模型版本记录于分析对象，供后续核对与审计。

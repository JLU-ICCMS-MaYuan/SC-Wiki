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

## 当前值支持依据契约补充（待实施）

- `POST /preflight` 和任务结果对同一字段分别返回当前值的 `status/reason`、已定位 `evidences`、来源类型及可选替换 `proposal`。`supported` 不得只由模型理由支撑；原文来源至少包含真实 `file_id`、可展示文件名、逐字引句与可用位置（PDF 页码，TXT/MD 章节或段落），派生来源须包含可复核输入和规则。
- 侧栏读取现有结果，不因打开字段调用模型。首屏直接显示状态、支持理由及第一条可核验依据；更多上下文和 PDF 区域仍可展开。`proposal` 不存在时不遮蔽当前值的证据。
- 引句定位失败、来源区域图片不可用和规则版本过期分别表达；图片失败不抹掉已保存引句，旧结果不得冒充当前 `supported`。未核对、缺证和无替换建议是三种不同状态。
- `POST /jobs` 的重查继续使用当前论文及附件、版本和权限约束；上传转论文与正式批准后仍可按稳定字段身份重读同一来源，不改写文件归属或人工决定。

## 人工修改与证据接口（待实施）

下列接口均在 `/api/rag/evidence` 下，`target` 仅允许 `upload`、`revision`、`paper`；按现有上传者、返修者、管理员/超级管理员权限鉴权，并核对当前字段的稳定 `item_key` 与 `expected_version`。文件 ID 和存储路径只由服务端产生。

| 接口 | 输入与行为 | 输出 |
| --- | --- | --- |
| `GET /{target}/{target_id}/manual/{item_key}` | 读取当前字段与历史版本的人工修改说明；只读、零模型调用。 | 可读差异、提交者、理由、缺证原因、证据条目及 AI 实际读取状态。 |
| `PUT /{target}/{target_id}/manual/{item_key}` | JSON：`expected_version`、当前值摘要、`reason`、`no_evidence_reason`、直接输入的文字证据及其来源说明。允许草稿不完整；服务端重算字段摘要，不信任客户端值或操作者。 | 新版本与当前人工记录；旧值已变化时返回 409。 |
| `POST /{target}/{target_id}/manual/{item_key}/files` | multipart：`expected_version`、来源说明、PNG/JPEG/WebP 截图或 UTF-8 TXT/MD。按实际内容校验类型和大小，拒绝伪装扩展名、不可读文件及越权上传。 | 证据条目 ID、原文件名、类型、大小和哈希；不返回磁盘路径。 |
| `GET /{target}/{target_id}/manual/{item_key}/files/{item_id}` | 同一目标权限下预览/下载私有证据，按服务端记录查路径和哈希。 | 安全的文字或图片响应，带不可执行的内容类型与下载文件名。 |
| `DELETE /{target}/{target_id}/manual/{item_key}/files/{item_id}` | 只允许删除当前用户尚未正式提交的证据；已提交项保留历史。 | 更新后的条目清单；实际文件在确认无引用后回收。 |

提交、返修提交及管理员批准在现有事务门禁中检查每个实际修改字段：`reason` 非空；`items` 为空时 `no_evidence_reason` 也非空；记录的值与来源版本必须匹配。失败返回按字段定位的 `manual_reason_required`、`manual_evidence_absence_reason_required` 或 `manual_evidence_stale`，不清除已保存草稿或文件。完整说明允许无论文出处的修改进入 `pending`，但结果仍为人工待审来源，不变成 `supported`；管理员批准继续执行独立的来源裁决。无实际值变化不要求人工说明。

`POST /jobs` 的审核 AI 从服务端加载已保存且匹配当前值的人工证据，以 `human_provided` 与论文原文分开输入；文本实际提供内容，图片实际传入可处理的图像或经校验的提取结果。模型不支持或读取失败时记录 `not_read` 并保留人工审核入口，不报告 AI 已核验，不把人工材料写成 `paper_quote`。图片、文本和来源说明都视为不可信输入，不执行其中指令。原 PDF 图像依据通过已授权文件及可靠页/区域定位按需呈现，不能拿人工截图替代系统原文。

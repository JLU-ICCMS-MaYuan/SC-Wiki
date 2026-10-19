# 字段来源接口

沿用 `/api/rag/evidence` 及现有上传草稿、科学保存和 Go 审核接口。

- `POST /preflight`：返回全部可浏览核对项，包括 `required=false` 的空字段。`needs_check` 仅针对需核对的当前断言。只读，不调用模型。
- `POST /jobs`：增加 `purpose`，默认既有 `check`；`review_all` 仅用于管理员论文审核，清空本次跳过缓存并把已有判断、建议和证据送入复核。保留指定重试、进度、取消与版本验证。
- 上传解析内部生成使用 `generate` 目的，不增加用户点击；有效推断或推测直接补入主表单，重建版本后页面读取同一核对结果契约。
- `proposal`：内部候选沿用 `values/evidences/supported/basis_kind/explanation` 校验；所有声称的引句都由服务端复核，推断与推测不得声称直接支持。补入后当前结果保存 `adopted_basis/ai_reason/auto_filled/auto_filled_content_hash/auto_filled_source_hash`，不把候选值作为侧栏第二套表单展示。
- `POST /proposals`、`prepare`、`finalize`：保留历史明确采用及管理员人工确认的版本契约；新上传的有效推断/推测在解析完成时已写入主表单，无须再次采用。管理员处理未获直接支持的值仍需理由。
- 上传提交：服务端仅允许与当前内容和来源摘要匹配的自动填写推断/推测进入待审，不授予 `human_confirmed`。
- `POST /prepare-review`：通用推测必须由服务端已保存、匹配当前版本的管理员逐项决定放行。Go 二次校验并持久化全部字段来源/建议；可选空项不作为有效断言批准。
- 失效、越权和保存失败沿用既有错误。迟到任务不得覆盖更晚的人工输入或批准结果。RAG 输出保留采用依据限定。

## 当前值支持依据契约补充（代码实施中，待完整验收）

- `POST /preflight` 和任务结果对同一字段分别返回当前值的 `status/reason`、已定位 `evidences`、来源类型及可选 `ai_reason`。`supported` 不得只由模型理由支撑；原文来源至少包含真实 `file_id`、可展示文件名、逐字引句与可用位置（PDF 页码，TXT/MD 章节或段落），派生来源须包含可复核输入和规则。
- 侧栏读取现有结果，不因打开字段调用模型。首屏直接显示状态、支持理由及第一条可核验依据；更多上下文和 PDF 区域仍可展开。“AI 理由”不呈现主表单值副本。
- 引句定位失败、来源区域图片不可用和规则版本过期分别表达；图片失败不抹掉已保存引句，旧结果不得冒充当前 `supported`。未核对、缺证和无替换建议是三种不同状态。
- `POST /jobs` 的重查继续使用当前论文及附件、版本和权限约束；上传转论文与正式批准后仍可按稳定字段身份重读同一来源，不改写文件归属或人工决定。

## 人工修改与证据接口（代码实施中，待完整验收）

下列接口均在 `/api/rag/evidence` 下，`target` 仅允许 `upload`、`revision`、`paper`；按现有上传者、返修者、管理员/超级管理员权限鉴权，并核对当前字段的稳定 `item_key` 与 `expected_version`。文件 ID 和存储路径只由服务端产生。

| 接口 | 输入与行为 | 输出 |
| --- | --- | --- |
| `GET /{target}/{target_id}/manual/{item_key}` | 读取当前字段与历史版本的人工修改说明；只读、零模型调用。 | 可读差异、提交者、理由、缺证原因、证据条目及 AI 实际读取状态。 |
| `PUT /{target}/{target_id}/manual/{item_key}` | JSON：`expected_version`、当前值摘要、`reason`、`no_evidence_reason`、直接输入的文字证据及其来源说明。允许草稿不完整；服务端重算字段摘要，不信任客户端值或操作者。 | 新版本与当前人工记录；旧值已变化时返回 409。 |
| `POST /{target}/{target_id}/manual/{item_key}/files` | multipart：`expected_version`、来源说明、PNG/JPEG/WebP 截图或 UTF-8 TXT/MD。按实际内容校验类型和大小，拒绝伪装扩展名、不可读文件及越权上传。 | 证据条目 ID、原文件名、类型、大小和哈希；不返回磁盘路径。 |
| `GET /{target}/{target_id}/manual/{item_key}/files/{item_id}` | 同一目标权限下预览/下载私有证据，按服务端记录查路径和哈希。 | 安全的文字或图片响应，带不可执行的内容类型与下载文件名。 |
| `DELETE /{target}/{target_id}/manual/{item_key}/files/{item_id}` | 只允许删除当前用户尚未正式提交的证据；已提交项保留历史。 | 更新后的条目清单；实际文件在确认无引用后回收。 |

提交、返修提交及管理员批准在现有事务门禁中检查每个实际修改字段：`reason` 非空；`items` 为空时 `no_evidence_reason` 也非空；记录的值与来源版本必须匹配。管理员批准准备结果携带人工记录 ID 与递增版本，Go 批准事务同时比较版本、字段值与来源摘要；准备后材料变化时拒绝本次批准。上传及返修转接在持有记录锁后重新检查理由和证据完整性。失败返回按字段定位的 `manual_reason_required`、`manual_evidence_absence_reason_required` 或 `manual_evidence_stale`，不清除已保存草稿或文件。完整说明允许无论文出处的修改进入 `pending`，但结果仍为人工待审来源，不变成 `supported`；管理员批准继续执行独立的来源裁决。无实际值变化不要求人工说明。

`POST /jobs` 的审核 AI 从服务端加载已保存且匹配当前值的人工证据，以 `human_provided` 与论文原文分开输入；文本实际提供内容，图片实际传入可处理的图像或经校验的提取结果。模型不支持或读取失败时记录 `not_read` 并保留人工审核入口，不报告 AI 已核验，不把人工材料写成 `paper_quote`。图片、文本和来源说明都视为不可信输入，不执行其中指令。原 PDF 图像依据通过已授权文件及可靠页/区域定位按需呈现，不能拿人工截图替代系统原文。

## PDF 局部证据响应补充

`POST /region` 请求沿用 `target/target_id/file_id/quote/pdf_page/block_id`；服务端使用已鉴权目标的 PDF manifest 和 SHA-256 决定实际文件，旧解析页码只作线索。`located` 响应增加 `dpi: 300`、实际 `pdf_page`、可选 `page_end`，以及按阅读顺序排列的 `crops[]`：每项包含 `pdf_page`、PNG data URL、原 PDF 点坐标 `clip_bbox_pdf`、输出 `width/height` 像素及相对裁剪图的 `highlights[]`；源扫描图不足 300 DPI 时附 `source_raster_dpi`。原有 `image/region` 保留为第一张局部图的兼容字段。无法唯一定位、文件变化或无可信区域时不返回伪造图片，并保留原引句及明确状态。

## 2026-10-11 当前人工证据接口调整

- `PUT /{target}/{target_id}/manual/{item_key}` 保持原 JSON 兼容，但新界面只发送 `reason`、`no_evidence_reason` 和空 `text_items`；旧直接文字记录按原接口可读。选择提供证据时将 `no_evidence_reason` 置空，选择不提供证据时要求当前附件为空。服务端以当前附件和缺证理由执行显式提交门禁，不信任前端选项。
- `POST .../files` 接受 PNG/JPEG/WebP、UTF-8 TXT/MD 及有效未加密 PDF，仍限制单文件 10 MiB、单字段最多 5 项。`source_description` 对新客户端可省略，由服务端根据安全文件名和真实文件类型生成；旧客户端传入的来源说明继续兼容。拒绝扩展名与内容不符、空白或损坏文件。
- `GET .../files/{item_id}` 对 PDF 返回 `application/pdf`、`inline` 和 `nosniff`，仍按目标权限与 SHA-256 验证。PDF 仅作为人工附件，不能使用原论文区域接口或被索引为论文原文。
- 审核 AI 只接收不超过 20 页且提取文本不超过 2 万字的可搜索 PDF 全文，保留 `human_provided` 身份；成功完成实际审核后才将该 PDF 标为已读。超限、无可读文本或失败时保持 `not_read`，供人工预览。旧 `text` 条目及已提交记录继续只读。

## 模型归纳字段的理由契约（2026-10-11）

`POST /preflight`、`POST /jobs` 的结果及正式来源读取沿用现有字段身份与版本，不新增 API：模型归纳记录返回 `check_mode=synthesis`、实际 `source_kind`、`reason`、可定位 `evidences` 和当前版本的 `ai_reason`。`ai_reason` 为简短的“本文依据 → 当前判断 → 局限”，不重复表单值或原文整段。`supported` 仍需要可定位本文依据；缺少具体理由时降为需重核，不能只在前端替换显示文案。

旧结果仅在内容与来源哈希仍匹配时可把具体 `reason` 用作当前 AI 理由；版本失效后只能列入历史。原文摘录、作者原列关键词、程序派生与人工改写按各自来源显示，不将核对理由误标为原文或人工决定。上传、返修及管理员/超级管理员共用此响应与侧栏规则。


## US11 字段影响隔离补充（已实现，验证边界见 field-isolation-validation.md）

- 继续使用现有 preflight/保存/复核接口。当前核对项已携带 `dependency` 与来源信息，前端补全可选类型并使用它，不新增端点或数据库列。
- 无关字段编辑不改变其他项的当前有效性、人工说明和提交资格；真实科学断言或其输入变化仍执行原版本和来源校验。只读打开、失焦、同值通知、重排不构成科学变更。
- 保存失败不能让未保存更改获得新核对资格，迟到 preflight/保存/复核响应不能覆盖更晚编辑；权限与批准门禁保持服务端约束。

## US12 正式细项、历史与 PDF 契约

- 沿用已有预检、保存、核对、建议、人工材料及区域 API。预测 Tc 返回各科学子项及其 record_field 定位；字段值与补丁仍写原 records，整记录科学验证保留。设置、来源、历史使用同一字段身份，标题不代理子项。
- 返回可选 audit_events，记录服务端实际 actor、带时区的 occurred_at、动作摘要及可选前后值和设置。旧粗记录历史标注 legacy_scope=record，不能把其 supported 映射为子项通过。未知作者、时间不伪造。
- 普通保存不接受客户端声明的审计身份或历史，按服务端前后值与认证用户生成。同值不追加改值事件；源值、准备版本及返修并发校验保持。修改事件与人工说明不替代审核或批准。
- /region、只读 /preflight 不要求可用模型配置，仍需认证与目标所属权限。缺可选区域 IR 时，只允许从同一授权原 PDF 可靠定位；文件不存在、身份或哈希不匹配、无法唯一定位时不能展示伪造或陈旧图片。
- 长引句可压缩显示，定位仍用完整 quote。区域和设置内容在页签、折叠时保持挂载，换来源后旧响应失效，渲染失败有明确提示与重试。

验证见[实施验证](../field-review-implementation-validation.md)。


## US13 展示约束

API、JSON与数据库不变。reason/status/stale仍按原契约返回；前端表单只消费输入校验消息，来源记录仅投影当前reviewFields供计数，不将reason伪装成schema_validation_failed。完整理由在当前字段侧栏正常文本展示，不能因隐藏重复正文清空状态、来源或人工资格。对应FR-053～057见[设计](../source-review-presentation.md)。

# 技术研究：用户指定上传文件身份

**依据**：[spec.md](spec.md)、[plan.md](plan.md)。

## 决策一：保留现有角色值，改产品名称

选择：main=论文正文、supplementary=补充材料、attachment=源数据文件。现有 paper_files、结构来源和前端类型已广泛使用这些值。改数据库枚举不解决用户问题，反而引入迁移及来源失联风险，因此不新增 raw_data 枚举。格式校验在统一 manifest 边界执行，不靠文件选择器 accept 保证。

## 决策二：新任务明确标记用户指定策略

create_task 是唯一新任务入口，服务器写入 file_role_policy=user-specified-v1；worker 校验后直接读用户角色。ScientificUploadDraft.state 原样保存 JSON，恢复不丢标记。拒绝仅靠“当前有一个 main”区分新旧，因为历史任务也可能恰有一个 main 且仍等待人工确认。旧 resolve-roles 与 assess_roles 只服务无标记历史任务，不扩散到正常入口。

## 决策三：维持既有来源和结构流

正文/补充材料进入分段及共享 text_sources，源数据沿用结构解析。引文从指定 main PDF 提取，文件身份检查独立保留。纠正文稿不新增自动覆盖原值的规则；既有冲突待审与人工编辑保护继续有效。本次不修改科学数值组装算法。

## 决策四：前端仅一份状态和一条上传队列

三处输入提供 role 参数；局部列表由同一 items 筛选。先校验文件，再将合法文件带稳定 clientId 追加。正文多选整体拒绝，避免静默挑选；单个错区或超限文件不影响同批其他合法补充材料。上传前允许逐项移除或清空；上传中禁用选择和修改。选择仅本地变动，不请求模型或全量校验。

## 调查证据

- MultiFileUploadPanel 现有 choose 将全部文件初始化为 attachment，Select 再改角色。
- upload_contracts.validate_manifest 当前未检查 main 数量，且没有角色/格式配对；#26 原始回归已声明恰好一个 main。
- upload_jobs 在完成文本提取后 assess_roles，会改写 role 或暂停；下游 all_chunks 与统一来源仅读 main/supplementary。
- upload_tasks.create_task 保存完整 JSON；scientific_evidence.persist_upload_state/restore_upload 不做字段白名单裁剪。
- #135 identity-consistency-fix.md 保留真实差异门禁，本轮不改变这项已确认行为。

# 材料家族归类与 AI 理由契约

`GET/PUT /api/rag/upload-tasks/{task_id}/draft` 沿用现有鉴权和论文级 `paper.material_families[]` 结构；响应可包含服务端生成的 `material_family_assessment` 与 `material_family_error`。保存草稿时客户端的分析对象不覆盖服务端记录；人工改选后旧分析不能为新值背书。目录或模型失败时其他字段可保存，材料家族为空；原有提交非空门禁不变。

`POST /api/rag/evidence/preflight`、核对任务结果及正式来源响应继续使用现有字段路径 `paper.material_families`。模型归类返回 `check_mode=synthesis`、实际 `source_kind=paper_synthesis`、可定位本文 `evidences`、核对 `reason` 和当前版本的 `ai_reason`；理由简述原文材料线索如何映射到目录分类及适用边界。旧记录 `ai_reason` 为空时，仅同版本、具体的 `reason` 可作为当前解释；否则返回需重新核对状态，不能显示“原文直接记载”。

新分类仅保留为 `pending`；无有效目录 ID、引句、理由或版本时不授予自动支持。上传者、管理员和超级管理员沿用既有权限，侧栏只读不触发模型；正式批准仍执行已有分类与人工裁决门禁。不增加 API 版本或数据库迁移。

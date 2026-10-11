# 研究驱动力 AI 理由契约

草稿 `GET/PUT /api/rag/upload-tasks/{task_id}/draft` 继续使用 `paper.research_motivation` 英文编号文本及服务端生成的 `research_motivation_error`；无需新 API。用户可编辑正文，客户端不能通过提交 `ai_reason` 为新值伪造模型归纳资格。

来源 `preflight`、核对任务及正式论文来源使用字段路径 `paper.research_motivation`。归纳记录返回 `check_mode=synthesis`、实际 `source_kind=paper_synthesis`、当前版本的 `reason/ai_reason` 和已定位的本文 `evidences[]`。AI 理由需说明每项动因由何种背景、缺口或目的陈述推得，避免把结果倒推为动机；只有理由和引句均有效时才可 `supported`。旧值、缺证、模型失败、人工改写或来源失效时按 [#109 共用契约](../../109-field-evidence-and-ai-suggestions/contracts/api.md) 提示重核，不回填空泛理由。

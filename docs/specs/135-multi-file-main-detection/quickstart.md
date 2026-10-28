# 验证：多文件主文识别

1. 用 La-Sc-H 的 SI、正文依次上传：预期正文自动成为 main、SI 成为 supplementary；检查两者文件 ID/哈希不变、引文来自正文、模型输入包含主文。
2. 用 H3S 正文、SI 顺序上传：预期无需确认、无错误角色改写。
3. 上传两篇独立论文或标题页不足的文件：预期 `needs_role_review`，无分段 LLM 调用；在 UI 选定角色后用当前 revision 提交并从已提取文本恢复。
4. 模拟旧 revision、非所有者、缺文件、多个 main 和并发确认：预期拒绝或幂等，不丢失已上传文件。
5. 单文件 PDF/TXT/MD 与结构附件回归；核对来源哈希改变时旧 AI 结果不为新角色背书。

## 本轮文件身份修复

定向测试：`test_document_identity.py`、`test_spectrum_submit_mysql.py`、`file-consistency-submit.test.tsx` 及 `file-identity-browser.mjs`。命令和验证边界见 [验收](identity-consistency-validation.md)。修正工具 `scripts/repair-upload-file-identity.py` 默认只盘点，`--verify-model` 为隔离来源验证，`--apply` 仅允许已有验证匹配的固定 La–Sc–H 任务。本次已完成，不需要用户重传或重新人工审核；其他任务不得套用此工具。

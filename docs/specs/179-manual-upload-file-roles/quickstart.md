# 验证指南：用户指定上传文件身份

**Spec**：[spec.md](spec.md)。

## 前置条件

由 python3 -m scripts.local_deploy.environment 获取项目环境，使用该环境 Python/Node。隔离任务、固定来源与临时文件验证；不调用真实上传/写入真实草稿。浏览器使用隔离 API 和真实 React 路由。真实原文模型调用如执行，记录来源、模型和复用/重跑步骤；不可用则明确保留未完成范围。

## 自动检查

- pytest 新增 test_manual_upload_roles.py，并运行 test_issue24_task_contract.py、test_issue24_task_repository.py、test_document_roles.py、test_role_review_api.py、结构和一致性受影响回归。
- Vitest 运行 manual-upload-files.test.tsx、upload-task-workspace.test.tsx、upload-model-headers.test.tsx 和 upload-role-review.test.tsx。
- npm run test:form-contract --prefix frontend。
- npm run test:form-contract:mutation --prefix frontend。
- npm run build --prefix frontend。

## 浏览器验收

在隔离前端启动后运行 manual-upload-files-browser.mjs。真实 /upload 页面分别选择一个正文、两个补充材料、两个结构文件，检查重复正文、错区、移除清空、零选择请求、上传清单以及 390px 布局；拦截全部 /api，禁止写真实服务。新任务没有角色确认。旧角色恢复与文件一致性另跑既有回归。

## 结果边界

执行证据统一记在 validation.md。通过 UI 不代表实际 PDF 全流程通过；固定模型响应回放不代表真实模型重提。历史正式论文和用户草稿不作为测试写入对象。远程链接/CI/部署与本地验证分开。

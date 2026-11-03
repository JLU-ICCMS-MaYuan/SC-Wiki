# 验证与验收

使用现有sc-wiki Python环境和frontend/node_modules。新测试仅写隔离目录/SQLite或隔离Redis键和数据库事务，保留真实用户草稿。

1. `python -m pytest backend/tests/test_parsing_workflows.py -q`：判断、完整窗口、未知/失败、Worker先选后解析及副本隔离。
2. `python -m pytest tests/01_decentralized_uploading/test_manuscript_handoffs.py tests/01_decentralized_uploading/test_workflow_binding.py -q`：SQL历史/快照及伪造保护。
3. `npm run test:field-contract --prefix frontend`、`npm run test:form-contract --prefix frontend`、`npm run test:form-contract:mutation --prefix frontend`：字段与四宿主回归。
4. Vitest运行 `tests/01_decentralized_uploading/typed-parsing-workflow.test.tsx`，执行TypeScript/Vite构建。
5. 从摘要已核实的原PDF/SI或已核对通用IR开始，隔离重跑受影响判断、专用提取与正式处理，记录源码、模型、来源、科学归属、保存重读和谱终态。真实调用不可用时记录未完成，不以回放冒充重提。

可复用 `scripts/verify-typed-parsing-workflow.py --task-id <实际任务ID> --output <新隔离目录>` 重新判断；针对本次CaH6样本另加 `--downstream`，从正文全部页及SI第1、2、3、19页重新提取相邻Tc字段，并让正式整理读取完整SI。该选项不代表对任意文献通用的科学验收，也不执行正式业务提交或整篇谱处理。

预期：仅匹配进入专用流程；不匹配/未知/失败专用调用为零。正式读写和四宿主保持绑定；既有失败由独立基线复现区分。

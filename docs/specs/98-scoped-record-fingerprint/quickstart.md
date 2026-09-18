# 验收方法

使用当前项目 sc-wiki Conda 环境，安全加载本地 `.env`（不要输出凭据）。集成测试必须明确指定 `SCWIKI_SUBMIT_TEST_TASK` 为已授权且尚未提交的真实任务；未指定时跳过。测试仅在当前 MySQL 外层回滚事务中写入，不建临时数据库，不修改 Redis 草稿。

```bash
PYTHONPATH=. SCWIKI_SUBMIT_TEST_TASK=92127c24cf034ac79845a8055ccc90b8 /home/mayuan/miniconda3/envs/sc-wiki/bin/python -m pytest -q backend/tests/test_issue98_submit.py
```

通过后从真实上传提交入口提交指定任务，核对论文为 pending、材料状态与 Tc 数值保留、三个来源指纹互异，重复提交返回同一论文 ID。正式提交会按既有流程清理临时草稿并保存审核快照，此后集成测试应选择新的已授权未提交任务。

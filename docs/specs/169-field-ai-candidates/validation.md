# 实施验证

日期：2026-10-28。分支：`mayuan`。关联 [Issue #169](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/169)。

## 已实现行为与证据

| 需求 | 结果与验证 |
|---|---|
| FR-001 / SC-001 | 保持提交按当前有效版本复用；人工通过、模型通过和应用候选后提交均不调用模型。测试对模型配置与调用入口设失败断言。 |
| FR-002 / SC-002 | 主动单字段提示允许对非空值提供独立候选；真实解析／校验／聚合函数用受控模型响应验证。当前人工通过不被模型撤销，新候选独立持久保存；迟到任务不越过较晚人工决定。 |
| FR-003、006 / SC-004 | 候选移入字段设置原值下方，显示可读值、独立理由、依据及应用按钮；顶部不再显示候选正文。旧候选不自动采纳，已解决事项不再显示待审候选。 |
| FR-004、005、007 / SC-003 | 准备只接受服务端候选令牌；实际保存后校验预期内容、来源及候选身份，再写真实人工通过。真实 MySQL／隔离 Redis 验证上传、返修、管理员三类目标的文本、列表、状态数值字段。 |
| FR-008 / SC-004 | 重复确认幂等，保存失败不确认，确认失败可原页重试或重开恢复；候选替换、内容变化、越权与并发未保存输入不误覆盖或误通过。应用前值和理由保留历史。 |

## 后端检查

使用 `/Users/mayuan/software/miniconda3/envs/sc-wiki/bin/python`，通过 dotenv 加载本地配置后执行 pytest；`SCWIKI_CURRENT_MYSQL=1` 显式启用 MySQL 外层回滚测试。

检查文件：

- `tests/01_decentralized_uploading/test_field_candidates.py`
- `tests/01_decentralized_uploading/test_field_decisions_mysql.py`
- `tests/01_decentralized_uploading/test_field_review_start.py`
- `tests/01_decentralized_uploading/test_two_stage_review.py`
- `tests/01_decentralized_uploading/test_two_stage_review_mysql.py`
- `tests/01_decentralized_uploading/test_property_evidence.py`
- `tests/01_decentralized_uploading/test_evidence_proposals.py`

最终组合：**71 通过、2 跳过**。跳过项为需要额外指定真实来源任务的既有性能测试。新候选文件的 17 项全部通过。数据库测试使用外层事务回滚；上传保存测试使用随机独立 Redis 键并在结束时清理，未修改用户草稿。

## 前端与浏览器

`frontend` 下运行 `npm run test:upload-ui -- ../tests/01_decentralized_uploading/field-ai-candidate.test.tsx ../tests/01_decentralized_uploading/two-stage-review.test.tsx`：**19 项通过**。

运行 `npm run build`：TypeScript 与生产构建通过；保留既有 3Dmol eval 和大分包提示。

`tests/01_decentralized_uploading/field-candidate-browser.mjs` 使用 Chrome、正式上传 React 路由和隔离 API，验证 1500px 与 390px 两种宽度：主动核对→查看候选→应用→刷新→提交。每个场景只出现 1 次主动模型任务、1 次提交检查，应用与提交不新增模型任务；页面错误为 0，侧栏无横向溢出。实际保存请求只修改研究驱动力字段，旧值与候选显示分开。

截图已目视检查：

- [桌面侧栏](assets/candidate-1500.png)
- [窄屏侧栏](assets/candidate-390.png)
- [请求与结果记录](assets/result.json)

## 既有测试边界

较广旧套件仍有既存失败：`upload-task-editor-layout.test.tsx` 4 项、`evidence-workflow.test.tsx` 19 项。以提交 `881583c9` 的独立源码快照运行对照，失败名称与本次工作树完全一致，未新增失败；涉及旧保存／审核接口与界面契约的夹具。本功能修改的顶部候选测试通过，不将旧套件整体写成通过。对照记录见 [基线比较](assets/baseline-comparison.json)。

## 验证限制与收尾

模型响应为受控夹具，未实际付费调用模型，也未评价论文科学结论正确性。浏览器验证正式上传宿主；返修和管理员目标由真实存储集成检查覆盖，不冒充三个登录角色的浏览器端到端验收。未自动应用 La–Sc–H 历史候选、未部署、未推送。

Overview 已回写实际行为。Issue 与本地 Spec 相互关联；远程 Spec 未推送，链接门仍待验证，因此保留 Issue 开放。

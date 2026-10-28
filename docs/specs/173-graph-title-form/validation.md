# 验证记录

日期：2026-10-28。分支：mayuan。关联 [Issue #173](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/173)。

## 已实现

原标题下方新增“图谱科学标题”输入框，读取真实草稿值，附用途与 `paper.knowledge_graph_title` 键名。复用 ReviewPaperTextField、setPaperField、EvidenceFieldMarkers 和 createFieldDraftSaver，连接来源核对、设置编辑、失效通知与局部保存。补齐可空类型及中英文文案。未改后端业务代码、数据结构或标题生成规则。

## 验证结果与需求对应

| 检查 | 结果 | 覆盖与边界 |
| --- | --- | --- |
| 修复前回归 | 未找到“图谱科学标题”输入框，失败符合原缺陷 | 测试初始化适配本机 Node 后才确认此失败，初始化错误不算缺陷复现 |
| 新增完整宿主测试 | 10/10 通过 | FR-001–007；有值、空串、null、缺失；精确字段 PATCH、重载、原标题不变；侧栏编辑与待核对；保存失败、只读、返修冲突。API 使用 Mock，控件、核对 Hook 和保存器使用真实实现 |
| 既有字段设置回归 | 13/13 通过 | 上传、返修和管理员字段设置及并发保护；连同新增测试共 23 项，补齐测试详情响应 token 后新增 10 项再次通过 |
| TypeScript 与 Vite 生产构建 | 通过 | `npm run build`；仅有既有大资源分块提示，未新增依赖 |
| 正式页面浏览器 | 1440px、390px 均通过，页面错误 0 | 实际路由 `/upload/tasks/<隔离任务>`，字段定位、用途、侧栏当前值、编辑、保存刷新、原标题不变、提交中禁用；每个视口一次保存、一次提交检查；业务 API 全部拦截，未提交真实论文 |
| MySQL／Redis 生产保存函数 | 3/3 通过 | 修改非空值、null 填写、清空；Redis 与 MySQL 重读一致，旧结果不再授信且保留为 stale，旧草稿版本写入返回 409 |
| 既有英文叙述字段测试 | 4 通过、1 个基线失败 | 图谱标题草稿保留、英文生成约定通过；旧摘要词数断言失败，见下文 |

## 存储隔离与环境

使用项目运行环境 `/Users/mayuan/software/miniconda3/envs/sc-wiki/bin/python`，仅在进程内加载本地 `.env` 并检查目标：MySQL `127.0.0.1:3307/scwiki`、Redis `127.0.0.1:6379/0`。通过 `SCWIKI_CURRENT_MYSQL=1` 显式启用测试。

MySQL 使用外层事务回滚，Redis 使用随机 UUID 任务／草稿／锁键并在 finally 清理；调用生产 `field_drafts.save_fields`、`upload_tasks.save_draft` 和 `get_draft`，没有模拟存储。测试只借用现有用户身份，不改真实用户草稿，不请求模型。

初版测试错误地认为旧内容缓存失效后仍返回同键的 unchecked 记录；实际生产路径不加载过期缓存，由 `public_snapshot` 生成待核对展示。已改为通过生产展示函数断言 unchecked，并单独验证历史读取为 stale。此处修正的是测试预期，未修改后端实现。

## 基线失败

`backend/tests/test_narrative_english_output.py::test_prompts_forbid_unsupported_narrative_content` 要求 `SYSTEM_PROMPT` 包含旧字符串 `100-200 words in English`；当前摘要提示已改为依据原摘要长度归纳，因此断言失败。

核对 `fd0a1f42` 的 extractor、paper_summary、upload_jobs 及该测试文件，与当前文件字节一致；从 HEAD 提取提示词赋值与原测试函数重新执行，仍为相同断言失败。证据见 [baseline-result.json](assets/baseline-result.json)。这不是本次字段接入引入的失败，未为通过测试修改无关摘要规则，也不将它计为通过。

## 浏览器证据

- [桌面表单](assets/form-1440.png)
- [窄屏表单](assets/form-390.png)
- [窄屏字段设置](assets/settings-390.png)
- [浏览器结果](assets/browser-result.json)

截图中的论文内容均为隔离测试数据。已实际查看表单与侧栏截图；字段、用途和键名在窄屏可见，侧栏支持换行。单行主表单输入框内的长标题可以横向编辑，侧栏显示完整可换行内容。

## 可复现命令

前端在 `frontend/` 运行：

```sh
npm run test:upload-ui -- tests/01_decentralized_uploading/graph-title-form.test.tsx tests/01_decentralized_uploading/paper-field-settings.test.tsx
npm run build
```

后端在仓库根、加载本地配置并核验本机目标后运行：

```sh
SCWIKI_CURRENT_MYSQL=1 python -m pytest -q tests/01_decentralized_uploading/test_graph_title_form_mysql.py backend/tests/test_narrative_english_output.py --tb=short
```

浏览器脚本使用现有本地 Vite `http://127.0.0.1:5173`；`PLAYWRIGHT_MODULE` 指向本机 Playwright，`CHROMIUM_PATH` 指向 Chrome，运行 `node tests/01_decentralized_uploading/graph-title-browser.mjs`。依赖路径说明见 [quickstart.md](quickstart.md)。

## 当前限制与收尾

本次只验证本地源码及隔离数据，没有部署、推送或修改用户截图所对应的真实草稿。没有验证生成标题的科学正确性。远程 Spec 文件未推送，双向远程链接检查保持未完成，Issue 保留开放。Overview 和根 README 已同步字段入口与操作说明。

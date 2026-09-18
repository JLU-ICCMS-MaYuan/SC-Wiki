# 数据源退役验收

## 前置条件

使用项目现有 Node、Go 与 sc-wiki Python 环境。真实接口验收要求本地 Go、Python、MySQL 可用；不要启动迁移或创建示例正式数据。所有本地 HTTP 操作仅查询。

## 自动回归

在仓库根目录执行：

```bash
npm --prefix "frontend" run test:upload-ui -- --maxWorkers=2 --minWorkers=1
bash "scripts/run-tests.sh" go
npm --prefix "frontend" run build
DATABASE_URL="sqlite:///:memory:" JWT_SECRET_KEY="test-only-secret-for-dataset-retirement"   /home/mayuan/miniconda3/envs/sc-wiki/bin/python -m pytest   "backend/tests/test_material_state_export.py" "backend/tests/test_structure_candidates.py"   "backend/tests/test_property_modules.py" "backend/tests/test_form_definitions.py"   "tests/07_researcher_community_forum/test_news_compose.py" -q
git diff --check
```

Python 命令的配置仅在测试进程中生效，不修改项目或系统环境。全量前端不得排除已知失败文件；预期零失败。Go 全量及相关 Python 用例、TypeScript 与 Vite 构建必须通过。

## 实际接口与页面

1. 使用由当前工作区源码运行的本地服务，确认健康检查可用。
2. 请求本地搜索，选择已公开论文，验证结果、详情和材料状态结构；无结构时显示空态。
3. 请求三个取消的 POST 路径，确认均不提供数据；同时查询 Python 表单定义等保留代理接口，验证代理仍工作。
4. 浏览器打开探索页，按元素或化学式搜索、查看结果和详情；确认无退役来源按钮，且正常请求不访问退役路径。
5. 对比代码、挂载与文档引用；Spec 和回归测试允许保留名称作为历史定义及断言。

## 结果记录

2026-09-11 使用当前工作区源码完成以下验证：

| 验证 | 结果 |
| --- | --- |
| 前端全量 | 35 个测试文件、299 项测试全部通过；包含新增 7 项本地搜索回归和既有上传、审核、证据工作流测试 |
| Go 全量 | `bash scripts/run-tests.sh go` 通过；覆盖本地查询、详情、权限、审核、统计和导出等已有测试 |
| 相关 Python | 20 项通过；结构候选、模块物性、表单定义、材料状态导出和 Compose 配置 |
| 生产构建 | TypeScript 与 Vite 通过；保留已有 3Dmol eval 和大分包警告 |
| 文档与原型 | Spec 无占位符、相对链接有效，SVG XML 与原型 JavaScript 语法通过；diff 无空白错误 |
| 真实 HTTP | 从当前 `goserver/` 构建临时二进制，在 18080 连接现有 MySQL 与 Python；四种本地搜索模式均返回 Hg 4.2 K、论文 #9；详情 200、不存在论文 404 |
| 退役与代理 | 三个取消的 POST 接口全部 405；保留的 `/api/rag/form-definitions` 为 200；受保护空间群接口匿名访问为 401 |
| 真实浏览器 | Chromium 从 Vite 加载当前前端，API 转发到上述临时 Go 服务，使用真实响应；完成化学式搜索、详情、3D canvas、CIF 文本与返回列表；页面异常为零，退役 API 请求为零 |

临时 Go 进程在验收后已停止；原本地服务未被替换。没有写入正式论文、审核状态或迁移数据库，没有执行生产部署。浏览器覆盖真实已有结构，空态、筛选、分页和重试由交互回归覆盖。

## 既有失败的消除

最小复现命令为：

```bash
npm --prefix "frontend" run test:upload-ui -- \
  "tests/01_decentralized_uploading/submit-validation-feedback.test.tsx" \
  -t "模块化物性错误汇总" --maxWorkers=1 --minWorkers=1
```

修正前该用例期望具体物性错误，却收到预检错误文案；修正 POST 端点替身后原断言通过。上传和批准测试现在显式让证据预检通过，再将指定错误注入最终提交；成功用例核对证据版本与仅一次最终提交。未修改上传、审核或证据核对的业务代码，未删除或降低原业务断言。


## 最终收敛

- FR-001–FR-007 均有实现、测试或文档证据；US1/US2 验收完整。
- 没有发现缺失、部分实现、设计冲突或超出已确认范围的生产改动。
- KISS/YAGNI：删除专属代码，不增加兼容分支；DRY/SOLID：复用本地查询和共享结构/物性读取，测试通过端点区分各自职责。
- 本次验证完成后按仓库要求提交；提交标识和 Issue 最终状态以 Git 与 #104 为准。未推送或部署到生产。

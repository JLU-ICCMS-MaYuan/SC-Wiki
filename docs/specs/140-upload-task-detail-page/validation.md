# 实施与验证：任务新标签页

日期：2026-10-16。分支：`mayuan`。

## 已实现行为

- 上传任务普通区域使用原生新标签页链接，地址为 `/upload/tasks/:taskId`，保留原上传列表与本地文件、多选状态；删除查看／收起按钮和列表下方详情。
- 独立任务页复用原有解析和校对工作区，按账号及地址任务重新挂载，不受旧活动任务缓存影响；保留重试、手填、角色确认、核对和提交回调。
- 详情顶部显示返回上传记录；无权限、失效任务不显示旧表单，已提交任务按现有接口结果进入正式论文。
- 原列表重新获得焦点时刷新索引。主表单未保存或保存中时提供浏览器离页保护；人工证据草稿仍使用原有保护。

## 前端测试

以下命令在本次工作区运行，8 个文件、79 项通过：

```bash
NODE_OPTIONS=--no-experimental-webstorage npm --prefix "frontend" run test:upload-ui -- \
  "tests/01_decentralized_uploading/upload-task-editor-layout.test.tsx" \
  "tests/01_decentralized_uploading/upload-task-workspace.test.tsx" \
  "tests/01_decentralized_uploading/upload-task-navigation.test.tsx" \
  "tests/01_decentralized_uploading/upload-task-single-clean.test.tsx" \
  "tests/01_decentralized_uploading/upload-task-batch-delete.test.tsx" \
  "tests/01_decentralized_uploading/manual-evidence-editor.test.tsx" \
  "tests/01_decentralized_uploading/property-spectra-navigation.test.tsx" \
  "tests/01_decentralized_uploading/upload-role-review.test.tsx"
```

日志：`/tmp/scwiki-140-final-tests.log`。Node 26 的实验性 Web Storage 与现有 jsdom 配合会使未加参数的测试在初始化时无法读取 localStorage；命令只对本次测试进程关闭该实验特性，不修改产品代码或全局环境。旧工作区测试中 λ、ωlog 仍按数字控件查找，已对齐现有文本输入和独立单位契约，未改变科学字段实现。

覆盖：地址直达／重挂载恢复、忽略旧缓存、401/403/404、已提交跳转、跨任务迟到响应、保留待上传文件与多选、清理与批量删除、保存后解除离页阻断、只读预览、人工证据及谱导航回归。正式提交仅验证既有回调路径，没有向真实论文提交数据。

## 实际浏览器验证

使用正式 `main.tsx`、AppShell、路由和上传／详情组件，在 `http://127.0.0.1:18441` 的隔离 HTTP 数据夹具下操作，不使用静态 Demo 替代组件。服务脚本：`/tmp/scwiki140-browser-server.mjs`，请求记录：`/tmp/scwiki140-ui-requests.json`。

1. 原上传页点击任务链接后，新增独立详情标签页；原上传页地址及另一任务的多选状态保留。另通过条框空白区域及卡片中心点击，均新增对应任务详情标签页，原列表不跳转。
2. 详情展示地址指定的文件名、阶段和完整校对入口，没有上传文件选择区；原列表没有查看／收起按钮或解析表单。
3. 在真实校对组件将标题改为“新标签页校对保存与刷新验收”，点击立即保存，界面显示已保存；刷新同一任务地址后恢复保存值。隔离 HTTP 日志包含对应草稿 PUT 和随后 GET。
4. 详情与列表分别在 1440px 和 390px 检查，页面 `scrollWidth` 等于 `innerWidth`，未新增横向溢出。视口测试后已恢复。
5. 修正夹具响应契约后，最终详情浏览器错误日志为 0。截图：`/tmp/scwiki-140-production-detail.png`（派生界面记录，不是论文证据）。

## 验证边界

- 本次不修改后端、数据库或模型，不执行迁移、批量修复、真实论文提交或部署；浏览器 API 数据为隔离夹具。
- 浏览器原生关闭页提示受客户端策略影响；主表单未保存／保存中的事件阻断与保存后解除已由组件测试验证。没有宣称所有浏览器均展示相同系统弹窗。
- 工作区含其他任务的未提交主文识别与表单改动；运行验证包含其现状。本次提交须只包含 #140 的增量，原有改动保留；独立提交内容的验证另记。
- Issue #140 保持开放；本地未推送，远程 Spec 双向链接尚未验证，不冒充已关闭或远程部署成功。


## 独立提交内容验证

为避免把其他任务的工作区改动误当作本次成果，将 HEAD 与本次增量组装到 `/tmp/scwiki140-clean-validation`，既有 #120/#135 未提交差异未纳入。该副本前端生产构建通过（`/tmp/scwiki-140-clean-build.log`），7 个测试文件、77 项通过（`/tmp/scwiki-140-clean-tests.log`）。验证文件为上述清单去掉未提交的角色确认测试；布局文件也去掉其已有的其他任务测试差异。共享文件经三方内容合并精确分离，本次提交不包含原有主文角色确认或生成质量改动；其工作区内容仍保留。

生产构建只有既有的 3Dmol eval 及大包提示。没有以工作区 79 项通过替代独立提交的 77 项验证，也没有把隔离 HTTP 草稿保存描述为真实 MySQL 验收。

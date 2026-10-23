# 验证记录

2026-10-23：12 项相关前端测试通过，覆盖失败来源不显示、sources 缺失不影响资讯、列表请求失败仍能重试、分类标签、自然周分页与历史入口。

从已提交 HEAD 单独导出前端，并仅覆盖本次三个前端文件后，TypeScript/Vite 生产构建通过。
当前工作区其他任务未提交文件没有进入隔离构建。构建存在项目已有 3Dmol eval 和 chunk 大小提示，不是本次新增错误。

命令（使用项目 Node 22）：

~~~sh
npm run test:upload-ui -- tests/07_researcher_community_forum/news-feed.test.tsx tests/07_researcher_community_forum/news-classification.test.tsx tests/03_data_search_and_database_discovery/news-page-layout.test.tsx
npm run build
~~~

删除引用搜索确认：SourceState、来源状态辅助函数、onSources 回调及该面板的中英文词典项不再保留；backend 和 Go API 没有本任务改动。
原图哈希与本地文档链接核验通过。生产发布结果在执行后追加，不以本地构建成功代替上线验证。

## 2026-10-23 生产发布完成

- 代码提交 8435f16 已推送。生产前端保持已运行的 eb8ce92 基准，仅叠加本 Issue 的 NewsFeed 和中英文 news 三文件；基准与补丁提交分别记录，未把当前分支其他前端功能当作已经部署。
- 发布前核验这三个文件在生产基准与本任务开始前 HEAD 间无差异；隔离构建再次通过。约 1.96 MB 制品包及全部静态文件 SHA256 在服务器验证一致。
- 新前端镜像及基准/补丁身份见 [activation.json](assets/verification/activation.json)。原发布配置保留在服务器 /home/mayuan/sc-wiki/backups/news156-20261023/，运行配置保留 FRONTEND_SOURCE_COMMIT 基准并新增 FRONTEND_PATCH_COMMIT 与制品清单摘要，明确这是定向前端补丁。
- 只重建 scwiki-app-frontend-1；其他 13 个服务容器 ID 不变，没有数据库迁移、采集状态修改或后端重建。
- 公网实际浏览器确认来源状态入口、告警、错误码、最后成功时间与 Phys.org 说明全部不存在；API 仍返回 13 条来源状态。资讯卡片的来源和分类仍可见，历史入口、返回本周和详情可用，390px 无横向溢出，无页面脚本异常或 5xx。
- [浏览器断言](assets/verification/results.json)、[桌面](assets/verification/desktop.png)、[手机](assets/verification/mobile.png)。这些是实际公网截图，不是 Mock 页面。
- 通过已认证 GitHub API 读取 mayuan 的 spec.md，核验远程可访问且正文链接指回 #156；保留其他任务未提交改动。

此次隐藏展示不代表来源采集错误已经修复；后台诊断和原有重试继续按原逻辑运行。

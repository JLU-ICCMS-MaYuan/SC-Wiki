# 验收说明：搜索默认首页

## 前置条件

在 `mayuan` 分支，已有前端依赖；使用项目 Conda 环境中的 Node 22。浏览器检查使用隔离端口和独立浏览器上下文。

## 自动检查

在仓库根目录执行，先将项目环境的 bin 加入当前命令的 PATH：

```sh
npm run test:upload-ui --prefix frontend -- tests/02_identity_governance/sidebar-navigation.test.tsx tests/02_identity_governance/auth-page.test.tsx tests/02_identity_governance/language-switch.test.tsx tests/03_data_search_and_database_discovery/search-navigation.test.tsx tests/03_data_search_and_database_discovery/search-results.test.tsx tests/03_data_search_and_database_discovery/local-search-regression.test.tsx tests/03_data_search_and_database_discovery/news-page-layout.test.tsx
npm run build --prefix frontend
```

构建验证可用 TypeScript 检查后将 Vite 产物输出至 `/tmp`，避免覆盖已有 `frontend/static`。

## 浏览器路径

1. 1440×900 访问 `/`，应到 `/search`，出现化学式输入及元素周期表；探索在热点前且高亮。
2. 点击热点，确认 `/news` 的热点内容；点击 SC-Wiki 回到搜索。分别验证展开、收起及中英文。
3. 填写化学式，原搜索入口应继续新开带参数的结果页；刷新结果 URL 仍有效。
4. 390×844 重新进入 `/`，默认图标侧栏，探索和热点均可用；输入后切换侧栏不丢失文本。
5. 认证无来源返回、登录成功、已登录进入认证及退出回到搜索；合法来源优先，注册默认账户规则有效。

结果、环境及局限记入 [validation.md](validation.md)。未推送或部署时不据此宣称远程站点生效。

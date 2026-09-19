# 验证指南：社区 Tc 双图比例

## 前置条件

前端依赖已安装；Node 可用；浏览器验收使用现有 Playwright 与 Chromium。运行前端时绑定回环地址，脚本拦截全部 API，不访问生产数据。

## 命令

在仓库根目录运行：

```bash
npm --prefix "frontend" run dev -- --host 127.0.0.1 --port 5191 --strictPort
node "tests/07_researcher_community_forum/chart-aspect-ratio-browser.mjs"
"frontend/node_modules/.bin/vitest" run --config "vitest.config.ts" "tests/07_researcher_community_forum/community-charts.test.tsx"
python -m pytest "tests/07_researcher_community_forum/test_issue30_tc_chart_preferences.py::test_chart_controls_share_responsive_layout" "tests/07_researcher_community_forum/test_issue30_tc_chart_preferences.py::test_both_charts_share_one_tc_domain_of_500k" -q
npm --prefix "frontend" run build
```

浏览器脚本默认使用 `http://127.0.0.1:5191`；可通过 `FRONTEND_URL` 指定本地地址。`PLAYWRIGHT_MODULE` 可指定已有 Playwright 模块绝对路径，`CHROMIUM_PATH` 可指定浏览器。截图及测量结果写入 `ARTIFACT_DIR`（默认 `/tmp/scwiki-111-artifacts`）。

本机可复用已安装工具：

```bash
PLAYWRIGHT_MODULE="/tmp/sc-wiki-browser/playwright/driver/package/index.mjs" CHROMIUM_PATH="/home/mayuan/.cache/ms-playwright/chromium-1223/chrome-linux64/chrome" node "tests/07_researcher_community_forum/chart-aspect-ratio-browser.mjs"
```

旧 Python 契约文件全量运行仍有 6 项历史断言失败，修改前为 7 项；不将其报告为全绿，详见 [验证记录](validation.md)。

## 预期结果

375、768、1440、1920、2560px 下高度误差不超过 1px；桌面双图对齐、侧栏切换后比例稳定；中英文窄屏控件与图例无裁切；字段、家族、空状态、背景、参考线、悬浮提示、详情正常。API 使用夹具，只证明前端行为，不代表部署或生产数据验收。

# 本地评审指南

当前交互预览已启动于 `http://127.0.0.1:5174/nobel-demo.html`；当前按用户要求使用原始照片，最终漫画后置。从仓库重新运行：

```bash
cd frontend
npm run dev -- --open /nobel-demo.html
```

Vite 默认地址为 `http://localhost:5173/nobel-demo.html`。如果 `5173` 已被占用，使用终端显示的端口。人物详情会由肖像链接在新标签页打开；也可在地址后加 `?person=onnes` 等人物 ID 检查详情模式。

建议依次检查：

1. 12 位人物是否都出现，头像是否能辨认。
2. 环形展陈是否缓慢转动，悬停/键盘聚焦是否暂停，移开后是否恢复。
3. 肖像下的姓名、年份、获奖时身份和获奖成果是否对应。
4. 详情页的经历和获奖贡献是否有对应可打开引用。
5. 键盘操作、窄屏布局以及系统“减少动态效果”设置。
6. 对照 `assets/portrait-manifest.json` 的 SHA-256 确认 Demo 图片即所列复用资产。

生产前端仍通过常规入口访问；本 Demo 不替换 `/news` 中现有内容。

浏览器回归：在仓库根目录运行 `node "tests/07_researcher_community_forum/nobel-demo-browser.mjs"`。需要本机 Chrome；脚本默认复用 `prototypes/account-center/node_modules/playwright`，也可通过 `PLAYWRIGHT_MODULE` 指定已有 Playwright 模块，`NOBEL_DEMO_URL` 指定预览地址。

第二轮评审：页面为白底与站点主色，头像边缘淡入白色；姓名跟随头像，按住左右拖动改变方向，主位最大。最新实测证据见 `assets/validation-v2/`，第一版证据仍保存在 `assets/validation/`。

第三轮评审：改为不遮挡的弧形展陈；主位更大，侧位转斜并缩小，姓名仍正向随照片移动。最新证据在 `assets/validation-v3/`；拖动一整圈检查主位交接和两侧间隔。手机优先完整呈现主位，左右拖动或索引查看其余人物。

## 正式页面本地验收

- 当前Vite地址：[快讯页展陈](http://127.0.0.1:5174/news#nobel-milestones)、[江崎详情](http://127.0.0.1:5174/nobel/esaki)。地址端口以Vite实际输出为准。
- `npm --prefix frontend run build` 构建正式页面；`npm --prefix frontend run preview -- --host 127.0.0.1 --port 4174`可独立查看编译产物。
- `node tests/07_researcher_community_forum/nobel-production-browser.mjs` 检查真实正式路由、中英文、份额、图片、新标签页和手机；通过 `NOBEL_SITE_URL` 可覆盖默认地址。
- Node 26环境运行Vitest需加 `NODE_OPTIONS=--no-experimental-webstorage`，避免Node自身未配置的localStorage覆盖jsdom实现。
- 本次仅源码接入与本地验证，不构成阿里云、Docker或镜像发布。

## 紧凑版本评审

当前可访问 `http://127.0.0.1:5173/news#nobel-milestones`。没有操作提示或暂停开关，默认自动旋转；索引选择后继续，悬停和键盘阅读仍可暂时停驻。索引紧随人物介绍，联系人位于索引下方。

执行 `NOBEL_SITE_URL=http://127.0.0.1:5173 node tests/07_researcher_community_forum/nobel-compact-browser.mjs` 验证两种语言、三种宽度的全圈间距、联系人和自动恢复。结果在 `assets/compact-validation/`。

## 11人名单核对

当前仅移除江崎，约瑟夫森和莱格特保留。正式页与Demo均为11个入口，`/nobel/esaki`不再展示人物详情；中英文引言为十一位/Eleven。1973年的历史共享说明仍列出江崎，与是否展出分开。新验证证据在 `assets/roster-validation/`。

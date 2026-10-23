# Demo 验证记录

日期：2026-10-23。Issue：[#159](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/159)。分支：`mayuan`。

## 已验证

- `npm run build`：TypeScript 与原应用构建通过；保留既有 3Dmol eval 和大包提示。原应用构建默认不包含独立 Demo HTML。
- 另以 Vite build API 指定 `nobel-demo.html` 为入口，输出 `/tmp/scwiki-nobel-demo-review-build/`，独立 Demo 构建通过。
- `frontend/src/demos/nobel/NobelDemo.test.tsx`：2 项通过，覆盖 12 位入口及新标签页属性、指定人物详情和来源。
- `tests/07_researcher_community_forum/nobel-demo-browser.mjs`：Chrome 真实浏览器验证通过，结果见 [browser.json](assets/validation/browser.json)。包括旋转、真实指针暂停/恢复、新标签页和空 opener、12 个详情及图像解码、引用锚点、390px 窄屏、减少动态、键盘切换。
- 截图：[桌面](assets/validation/desktop.png)、[人物详情](assets/validation/detail.png)、[手机减少动态](assets/validation/mobile-reduced-motion.png)。
- 原图与预览图哈希见 [portrait-manifest.json](assets/portrait-manifest.json)。它证明文件对应关系，不证明漫画质量或图片许可通过。

## 资料核验

- 使用浏览器 User-Agent 后，12 位获奖人的 Nobel Prize `facts/`、`biographical/` 页面均可获取。早先无 User-Agent 的 HTTP 403 不代表这些页面永久不可访问。
- 人物生卒年份读取了事实页；包括 Cooper 2024、Giaever 2025、Leggett 2026 年逝世信息，不沿用旧站的在世状态。
- 已阅读官方传记核对教育、任职和主要研究经历。Bednorz 的学习经历修正为先化学、后晶体学。
- 2003 年官方新闻稿明确记载 Abrikosov 的美俄身份、Ginzburg 的俄罗斯身份、Leggett 的英美双重国籍。Giaever 传记记载 1964 年入籍美国；Leggett 传记记载 2002 年获得美国国籍并保留英国国籍。
- 修正了初稿错误：2003 年三人各获三分之一，并非“共同获一半”；1986 年铜氧化物发现约 35 K，未达到液氮温区。
- 1913 年不存在本任务尝试的 `press-release/` 页面，改用 `summary/`；其余四个年份新闻稿已验证 HTTP 200 并读取相关内容。
- 六个原始论文 DOI 均可解析到出版者页面；Springer 页面返回带 Cookie 提示的跳转，仅据此不能声称已经核实全文。

## 后续阶段的验收项

- **最终漫画素材**：本地 Core Image 线稿处理与参考图相比仍有细节不清、噪点和画风不一致，不能作为最终资产验收。现有图片只供交互预览。用户要求 Demo 与最终网站使用同一素材，该条件仍未满足。
- **图片生成方式**：用户选择“先看交互，最终漫画稍后制作”，本轮不调用图片 API，未产生图片 API 调用费用。
- **外部来源与许可**：旧图确实来自 Git 历史，但逐图外部作者、来源和使用许可未完成核验。
- **科研内容**：详细人物文章和全部国家身份的逐项核验尚未全部完成；当前说明是初稿，不能声称全量史实审校通过。
- **生产接入**：未替换 `/news`；未部署、未推送；Issue 保持开放。

用户明确选择先评审交互后，本轮范围缩小为已验证的交互预览，允许按仓库规则作本地阶段提交。最终漫画及全部内容审校继续保持未完成，不将阶段提交等同于完整 Feature 验收或生产接入。

## 第二轮验证（六项用户反馈）

- 最新截图与检查结果保存在 [validation-v2/browser.json](assets/validation-v2/browser.json)，第一版记录留作历史。
- 使用原始照片：12张当前展示图与历史源图 SHA-256 逐一相等；原线稿资产保留但没有页面引用。
- 白底、无相框、无照片滤镜、渐隐遮罩、每个人物容器内的姓名与资料通过浏览器样式/结构检查；已目视检查桌面和390px手机截图。
- 自动旋转、悬停暂停和恢复、鼠标正反拖动、拖动不触发链接、释放方向延续通过真实浏览器检查；普通点击新标签页及空 opener 不变。
- 主位缩放大于侧位；拖动过程中姓名与照片中心保持对齐。12个人物可通过索引到主位。
- 触屏采用 Chrome 的真实 touch 输入，左右拖动和取消后恢复操作通过。修复了隐式捕获从图片交给舞台时，冒泡 lostpointercapture 误清空手势的问题。
- 12个详情页原照、段落引用锚点、键盘聚焦、减少动态和手机无横向溢出通过。
- TypeScript 检查、2项Vitest与独立Demo生产构建通过。不将交互测试当成最终漫画或科研史实审校通过。

# 技术与事实研究

**Issue**：[#159](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/159)

## 现状调查

- 生产页面触点：`frontend/src/pages/NewsPage.tsx` 的 Nobel Milestones 区块。
- 当前五个年份分组和获奖成果说明：`frontend/src/i18n/zh/news.ts`、`frontend/src/i18n/en/news.ts`。
- 旧版头像来源：提交 `6f5137139fffb167420dad250175e3c950401959`，旧路径 `frontend/static/img/nobel/`；旧前端迁移后不再位于当前工作树。
- 旧头像恢复位置：`assets/source-portraits/`。其中人物各一张，共 12 张；肖像尺寸差异明显，John Schrieffer 文件仅 100×141，部分照片不足以支持高质量放大。
- Demo 将与生产页隔离；当前 React、Vite、TypeScript 和 Vitest 已安装，无需新增依赖。

## 设计决策

### 决策：先做隔离 Demo

- **理由**：用户明确要求先评审视觉和交互。隔离入口不会提前改写生产新闻页，也允许先核验人物资料、图片和素材授权。
- **备选**：直接替换 `NewsPage.tsx` 区块。拒绝，因这会把尚未评审的视觉选择直接进入生产体验。

### 决策：复用同一组成品肖像文件

- **理由**：Demo 引用正式候选图片路径，并以哈希清单锁定内容，避免演示图片与上线素材分叉。
- **约束**：源图出处和许可不能从旧 Git 记录得出。来源/许可未清楚前只供仓库本地 Demo 评审，不完成公开发布验收。

### 决策：CSS 3D 圆柱，不增加 3D 库

- **理由**：需求只需固定环形队列绕 Z 轴旋转和悬停暂停；现有 CSS transform 可满足，避免新增 Three.js 等依赖。
- **交互**：用 `animation-play-state` 控制指针悬停和键盘焦点；尊重减少动态设置；人物详情通过带 `rel="noopener noreferrer"` 的新标签页链接打开。

### 决策：人物内容与引用一起维护

- **理由**：每一项出生/逝世时间、身份与贡献必须能追到对应来源，避免把官方授奖理由、历史国籍及广义科研影响混成一段不可核查的文本。
- **来源顺序**：Nobel Prize 官方事实页与奖项页；人物或实验的原始论文（DOI/出版者记录）；必要时采用国家科学院、大学、研究所等权威传记页补足生平。新闻文章和无署名聚合页不作主要依据。
- **领域边界**：2003 年 Leggett 的诺奖核心贡献是超流氦-3 理论；详情说明其与超导领域并列呈现的背景，不将其说成以超导工作获奖。

## 图片素材盘点

以下 SHA-256 是从历史提交恢复后的原图字节校验。存储位置均为 `assets/source-portraits/`。

| 人物 | 历史文件 | SHA-256 | 当前外部出处/许可 |
|---|---|---|---|
| Alexei Abrikosov | `AA_Abrikosov_ANL1.jpg` | `108352dbbc223c774ee9893e93e8bf238a93c1ca304ae5fce16061f0357d3880` | 待查 |
| John Bardeen | `Bardeen.jpg` | `037148c5fac3af34c1cf4b0a83514021244aa1604b13a9530226cd8705418e99` | 待查 |
| Brian Josephson | `Brian_Josephson,_March_2004.jpg` | `9068b3a84bc6e4c46e819b4ed975c9d287ff6c9036431bcded364260d6b99187` | 待查 |
| Georg Bednorz | `Georg_Bednorz_speaking_at_the_groundbreaking_of_the_new_IBM_and_ETH_Zurich_Nanotech_Exploratory_Technology_Lab.jpg` | `52506a9a8bbdb4361b459383756c89cc3fb97f74c01304f254e5a764f5cbb0fa` | 待查 |
| Vitaly Ginzburg | `Ginzburg_in_MSU_opaque.jpg` | `11bdaebfb04906287c9c90cbcd132e3cf9dc3be367ab844fe3c8fa6725745954` | 待查 |
| Ivar Giaever | `Ivar_Giaever.jpg` | `8610b6547332f172c25be761354c0bddb9017a0a8fedd1ff61ef6c09d63d876c` | 待查 |
| John Schrieffer | `John_Robert_Schrieffer.jpg` | `9a8aa97b140bdbbabcee17105638b835f4aa51d2e257e60a89304faee6499439` | 待查 |
| Heike Kamerlingh Onnes | `Kamerlingh_portret.jpg` | `3b46fccd0cfa0875e3aed23cd3373ec34f9ec1140fd2e107bf0beed3bb62b4fd` | 待查 |
| Alex Müller | `Karl_Alexander_Mueller.jpg` | `3a4550645a87fb4fd8dd95cb3b6e1ebb39d37bb2780909c369bd237204313b87` | 待查 |
| Leon Cooper | `Laureate_Leon_Cooper.jpg` | `443abdb2b3012faa65135a0f4f5ad6c38c6f74f65bab00463ca7075f6ead9c1d` | 待查 |
| Leo Esaki | `Leo_Esaki_1959.jpg` | `879c271f54b5a8e6cf59eb2a6de60adb4522eff4e4b19ceebdf67efe43b49410` | 待查 |
| Anthony Leggett | `Nobel_Laureate_Sir_Anthony_James_Leggett_in_2007.jpg` | `facf654f080f9611c03c86a0c281ee7eb3745fadd11f0b996017df23ffeb4b72` | 待查 |

恢复图像的 EXIF/注释可提供拍摄器材、软件和部分说明文字，但不能单独确认版权人或再使用许可。详情中要保留逐图来源字段，不能因图片曾在旧版网站显示而自动将许可状态视为通过。

## 官方资料与论文候选

以下 DOI 用于开展权威核验；实施前仍需实际打开并核对每条来源与陈述的对应关系。

| 年份/人物 | 候选原始论文或官方入口 | 用途 |
|---|---|---|
| 1913 Onnes | [Nobel Prize 1913 Physics](https://www.nobelprize.org/prizes/physics/1913/summary/)；Onnes, *The resistance of pure mercury at helium temperatures* (1911) | 奖项理由与汞超导发现时间线 |
| 1972 Bardeen、Cooper、Schrieffer | [Nobel Prize 1972 Physics](https://www.nobelprize.org/prizes/physics/1972/summary/)；Bardeen, Cooper & Schrieffer, *Phys. Rev.* 108, 1175 (1957), [doi:10.1103/PhysRev.108.1175](https://doi.org/10.1103/PhysRev.108.1175) | BCS 理论与获奖理由 |
| 1973 Esaki | [Nobel Prize 1973 Physics](https://www.nobelprize.org/prizes/physics/1973/summary/)；Esaki, *Phys. Rev.* 109, 603 (1958), [doi:10.1103/PhysRev.109.603](https://doi.org/10.1103/PhysRev.109.603) | 半导体隧穿效应与个人获奖部分 |
| 1973 Giaever | 同上；Giaever, *Phys. Rev. Lett.* 5, 147 (1960), [doi:10.1103/PhysRevLett.5.147](https://doi.org/10.1103/PhysRevLett.5.147) | 超导体电子隧穿与个人获奖部分 |
| 1973 Josephson | 同上；Josephson, *Phys. Lett.* 1, 251 (1962), [doi:10.1016/0031-9163(62)91369-0](https://doi.org/10.1016/0031-9163(62)91369-0) | Josephson 效应理论预言与个人获奖部分 |
| 1987 Bednorz、Müller | [Nobel Prize 1987 Physics](https://www.nobelprize.org/prizes/physics/1987/summary/)；Bednorz & Müller, *Z. Phys. B* 64, 189 (1986), [doi:10.1007/BF01303701](https://doi.org/10.1007/BF01303701) | 铜氧化物高温超导发现与获奖理由 |
| 2003 Abrikosov、Ginzburg、Leggett | [Nobel Prize 2003 Physics](https://www.nobelprize.org/prizes/physics/2003/summary/)；Abrikosov, *Sov. Phys. JETP* 5, 1174 (1957)；Ginzburg & Landau, *Zh. Eksp. Teor. Fiz.* 20, 1064 (1950)；Leggett, *Rev. Mod. Phys.* 47, 331 (1975), [doi:10.1103/RevModPhys.47.331](https://doi.org/10.1103/RevModPhys.47.331) | 分别核对 II 型超导理论、GL 理论和超流氦-3 理论 |

**访问状态**：当前网络核查尝试中，`api.nobelprize.org` 返回 HTTP 403，因此尚未逐页确认官方页面可访问或人物资料字段。上表是候选引文，不可视为已核验完成。下一步应使用浏览器/出版社页面确认并记录访问结果；若来源不可访问，则换用等价权威来源并注明。

## 后续核验与限制

官方网站 HTML 页面在设置正常 User-Agent 后已可访问，覆盖12人事实页、传记和奖项页面；访问结果与实质核对记录见 [validation.md](validation.md)。1987 年 Müller 的有效路径为 `muller`，不是 `mueller`。旧照片经过 Core Image 处理仍未满足参考漫画画风，当前 `frontend/public/img/nobel/comic/` 仅作交互预览资产。不得将此前的“候选资产复用”设计描述视为最终素材已完成。

## 第二轮实施方案（替代第一版动画与视觉）

恢复原始 JPEG 到 `frontend/public/img/nobel/original/`，按 SHA-256 核对与历史原照一致。白底和 SC-Wiki 主色，照片以透明遮罩淡入白底，删除相框及滤镜。人物姓名/资料成为同一移动容器的内容。用单一角度状态、requestAnimationFrame 和 Pointer Events 驱动圆柱水平投影；按角度计算水平位置、深度、缩放和层级，最近人物最大。拖动阈值区分点击与拖动，拖动时捕获指针，取消事件也释放状态。CSS 自转被替代，避免两个动画同时争夺角度；不新增依赖。

## 第三轮布局决策（替代第二轮 sin 横向投影）

圆柱两侧的 sin 投影压缩横向距离，叠加主位放大后会遮挡。仅增大半径不能保证全相位间隔。改为按有序循环相位计算缩放尺寸，再按相邻半宽之和加固定间隙排列；用中心两个人物的相位插值确定舞台原点，保持主位交接连续。照片侧倾用CSS透视，文字保持正向；布局按整个人物容器宽度保留间隙，所以图片和名字均受保护。不新增依赖，角度/拖动/暂停仍沿用同一状态。FR-012/013 → projection.ts与CSS → T015/T016 → 密集相位数学不变量及真实浏览器边界扫描。

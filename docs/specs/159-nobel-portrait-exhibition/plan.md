# 实施计划：超导诺奖得主漫画肖像展陈

**Issue**：[#159](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/159)

**日期**：2026-10-23

**Spec**：[spec.md](spec.md)

## 摘要

阶段调整：用户明确选择“先看交互，最终漫画稍后制作”。当前先交付已验证的交互预览，最终漫画与内容审校在后续阶段完成；不调用图片 API，也不直接接入生产页。

先提供隔离的 Vite Demo，不改快讯页生产区块。恢复的 12 张原照将以同一套固定处理产出漫画化肖像，由展陈和人物详情共用；人物资料以 Nobel Prize 官方人物页、奖项页与支撑具体成果的论文为引用。通过 URL 查询参数在新标签页打开人物详情。

## 技术上下文

- **语言与版本**：TypeScript / React 19，Vite 5，项目既有 Node 工具链。
- **主要依赖**：仅使用现有 React、CSS、Vite；不增加运行时依赖。
- **数据存储**：不使用后端或数据库；Demo 数据为项目内静态 TypeScript 数据。
- **测试体系**：根目录 Vitest 配置使用 jsdom；前端 `npm run build` 执行 TypeScript 与 Vite 生产构建。
- **目标平台**：本地浏览器，通过 Vite 开发服务器查看。
- **性能目标**：12 张经过裁切/压缩的肖像；动画通过 CSS 复合变换运行，减少动态模式下停用动画。
- **约束**：不接入真实 `/news` 页面；引用按人物资料字段关联；肖像外部授权未核实前只作本地 Demo 评审。
- **规模范围**：12 条人物资料、12 张原始肖像和 12 张漫画候选资产。

## 质量门

| 约束来源 | 强制要求 | 设计如何满足 | 状态 |
|---|---|---|---|
| AGENTS.md | 默认使用 `mayuan`；显式暂存本任务文件 | 写入和提交前核对分支；保留其他工作区改动 | 通过 |
| AGENTS.md | 不推送，不擅切分支 | 本地代码、文档与 Demo，用户评审后再决定接入 | 通过 |
| Issue #159 | 12 位获奖者、Demo 先行、最终图片复用 | 静态资料清单和共享图片资产目录 | 通过 |
| Spec FR-002/008 | 圆柱旋转、悬停暂停、键盘与减少动态支持 | CSS 3D transforms 和 focus-within/reduced-motion | 进行中 |
| Spec FR-005/006 | 新标签页详情与逐条引用 | `?person=<id>` 详情视图和字段级参考文献 | 进行中 |
| 版权边界 | Git 历史不能证明素材许可 | 单独维护许可状态；不宣称公开发布授权已完成 | 阻断公开发布 |

## 文件结构

```text
docs/specs/159-nobel-portrait-exhibition/
├── assets/
│   ├── IMG-001-nobel-timeline.png
│   ├── IMG-002-cartoon-reference.png
│   ├── source-portraits/             # 从 Git 历史恢复的原始字节
│   └── portraits/                    # Demo 和未来网站共享的漫画候选资产
├── checklists/requirements.md
├── research.md
├── plan.md
├── quickstart.md
├── spec.md
└── tasks.md
frontend/
├── nobel-demo.html                   # Vite 独立 Demo 入口
└── src/demos/nobel/
    ├── NobelDemo.tsx
    ├── data.ts
    └── nobel-demo.css
```

**结构选择**：把评审入口和生产路由分开，确保启动 Demo 不更改 `/news`。人物事实、图片映射与引用共置于静态数据文件，减少两类详情视图的内容分叉。CSS 3D 已足够完成小规模环形展示，无需引入 Three.js。

## 需求到设计的映射

| 来源 | 设计组件/接口 | 验证方式 |
|---|---|---|
| FR-001/003、US3 | 图片清单与 `assets/portraits/` | 检查 12 项路径均可读取；比对 Demo 使用的资产哈希清单 |
| FR-002、US1 | 圆柱 `.nobel-carousel` CSS 动画 | 浏览器检查旋转；悬停与键盘聚焦时 animation-play-state 为 paused |
| FR-004 | 当前人物资料卡 | 对照静态资料和官方页字段 |
| FR-005 | `?person=id` 详情模式 | 点击后 `target=_blank` 打开并显示相应人物详情 |
| FR-006、US2 | 每条经历关联 `citations[]` | 逐一打开引用 URL，核对它实际支持对应陈述 |
| FR-008 | focus-visible、prefers-reduced-motion 样式 | 生产构建、键盘走查和减少动态媒体样式检查 |

## 阶段与依赖

1. 为全部 12 位人物核对官方人物页与奖项授奖理由，补充可访问的原始论文/权威来源。
2. 固化肖像加工方法和候选素材；登记每张图的源文件、许可状态、输出哈希。
3. 建立独立展陈/详情 Demo 和 responsive CSS。
4. 执行构建、自动化与真实浏览器交互验证，形成用户评审入口。

## 必要复杂度

| 必要复杂度 | 为什么需要 | 已拒绝的简单方案及原因 |
|---|---|---|
| 人物内容按引用逐条关联 | 获奖理由、超导相关性和科学史常被混为一谈，必须让读者核查具体说法 | 在页面底部放一个泛化参考书目，无法追溯单条事实 |
| 独立 Demo 入口 | 用户要求先评审，生产区块不能提前切换 | 直接改 `/news` 会让未评审设计成为默认生产行为 |
| source/output 肖像双清单 | 后续网站需复用同一最终候选文件，也需保留素材来源和转换证据 | 只把加工结果放进组件目录，会丢失溯源和许可状态 |

## 第二轮实施方案（替代第一版动画与视觉）

恢复原始 JPEG 到 `frontend/public/img/nobel/original/`，按 SHA-256 核对与历史原照一致。白底和 SC-Wiki 主色，照片以透明遮罩淡入白底，删除相框及滤镜。人物姓名/资料成为同一移动容器的内容。用单一角度状态、requestAnimationFrame 和 Pointer Events 驱动圆柱水平投影；按角度计算水平位置、深度、缩放和层级，最近人物最大。拖动阈值区分点击与拖动，拖动时捕获指针，取消事件也释放状态。CSS 自转被替代，避免两个动画同时争夺角度；不新增依赖。

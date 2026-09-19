# 技术决策：Tc 双图比例

## 固定容器比例

- 决策：共享 4/3 常量，以 CSS `aspect-ratio` 确定高度，Recharts 响应父容器。
- 理由：宽度来自真实卡片空间，侧栏及窗口变化由现有 ResizeObserver 处理。
- 备选：固定高度无法约束形状；整体缩放 SVG 会缩放文字；额外自建监听器重复现有能力。
- 证据：现有 `ResponsiveContainer width="100%" height={minHeight}` 和两个 `minHeight={390}` 调用是扁长的直接原因。

## 控件和图例

- 决策：选择框维持 210/190px 标准宽度，增加最大宽度并允许容器换行；图例用最低高度，内容可向下展开。
- 理由：375px 窗口包含 64px 侧栏和页面/卡片边距，容不下两选择框。现有图例 `height: 92` 与 `overflow: hidden` 会隐藏后续项目。
- 备选：固定整张卡片比例会挤压内容；缩小全部字体伤害可读性；裁切图例使筛选入口不可达。
- 对齐依据：两图控件种类、宽度和目录相同，选中项仍用摘要。字段提示保持单行，图例置于比例容器外。

## 验证边界

- 决策：浏览器加载真实页面和 AppShell，只拦截 API 返回夹具，不替换布局/ResizeObserver。
- 理由：现有 Vitest 将所有 getBoundingClientRect 固定为 800×390，不能验证实际响应式尺寸。
- 备选：源码断言只能证明配置存在，不能证明两图在页面中的真实对齐或无溢出。
- 不涉及后端、持久数据或生产调用。

## 点选论文详情事件

- 浏览器回归发现旧 `ScatterChart.onClick` 读取 `activePayload` 无法打开详情；截图中悬浮提示正常，点击后没有详情请求。
- Recharts 2.15 的 ScatterChart 使用 `item` 事件；`getMouseInfo` 返回坐标而不带散点 payload。`Scatter` 的点事件由 `adaptEventsOfChild` 传入实际点及其 payload。
- 决策：将现有论文点击回调绑定到数据点的 `Scatter.onClick`，直接传递该点 payload；背景等值线不绑定点击，公共回调和数据契约不变。
- 该修复满足 FR-004 的既有验收；不增加交互功能或数据读取路径。

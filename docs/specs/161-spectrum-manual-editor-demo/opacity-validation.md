# 原图不透明度竖向滑条验收

对应 FR-030、FR-031 / SC-021。

- 编辑画布左侧、详情“原图与提取结果”卡片内容左侧均使用共用竖向控件，0–100%、步长1%，默认100%。
- 实际鼠标竖向拖动与方向键通过；Home到0%，End到100%。几何边界验证滑条高度远大于宽度，且位于图窗左侧。
- 0%时仅SVG原图透明，曲线路径和坐标轴保持；隐藏图模式禁用并保留值，恢复显示沿用原值。
- 编辑/返回/保存后保持百分比；只调透明度不触发数据未保存提示，不写localStorage谱文档、不改变数据点或撤销栈。
- 58个Chrome浏览器场景通过，含390px布局、原有选点/缩放/保存/零频流程；TypeScript与Vite构建通过。无业务API请求、无下载、无页面脚本错误。
- [机器记录](assets/opacity-browser-validation.json)、[详情](assets/opacity-demo-alpha-detail.png)、[编辑器](assets/opacity-demo-alpha-editor.png)、[窄屏](assets/opacity-demo-mobile-detail.png)。已查看渲染截图核对位置与透明度效果。

用户 dragInfluence.ts 前后 SHA-256 均为 `b3c8c9e32bfe0698f80def9171844e26b819e0c50e5e3feaebb62a049311f4e0`，已有参数改动不纳入本次提交。只修改独立Demo，不改正式详情或数据库；未推送。

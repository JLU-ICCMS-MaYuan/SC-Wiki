# Demo 验收记录

日期：2026-10-26。范围为 #161 独立人工调整 Demo，不包含真实数据库写入、正式详情接入或科学准确性验收。

## 自动验证

- `npm --prefix docs/specs/161-spectrum-manual-editor-demo/demo test`：19 项全部通过。
- `npm --prefix docs/specs/161-spectrum-manual-editor-demo/demo run build`：TypeScript 检查与 Vite 独立构建通过；构建产物不提交。
- `npm --prefix docs/specs/161-spectrum-manual-editor-demo/demo run test:browser`：25 个场景通过。真实 Chrome 中执行鼠标拖动、框选、滚轮缩放、数值输入、标定、保存、刷新与存储失败，不替换编辑核心。
- 机器可读结果：[browser-validation.json](assets/browser-validation.json)，页面脚本错误 0、业务 API 请求 0、下载事件 0。

## 验收映射

| 成功标准 | 实际证据与结论 |
| --- | --- |
| SC-001 | α²F 与 PhDOS 均从详情进入全屏编辑并保存返回；PhDOS H 调整后 La/Sc 数据与原始快照逐点相等。 |
| SC-002 | 正反轴映射往返；图上拖动和坐标输入一致；鼠标中心放大保持锚点；平移和适应窗口有效；标定修改后全部源像素位置相等。 |
| SC-003 | 单元测试覆盖平滑衰减、范围外/片段/分波隔离、越界和频率交叉约束；浏览器实拖中心与邻点变化、其他片段不动，二维单点不改邻点。 |
| SC-004 | 只标记零频时仍为不完整；随后在原图零频线上点选才记录当前曲线零频点，其幅值取自点击位置而非自动设零；不生成 λ/ωlog 或科学采纳。 |
| SC-005 | 一次拖动一次撤销，重做精确恢复；恢复初始也可撤销；保存刷新保持；三种退出动作、未应用标定、配额异常与损坏 JSON 分别通过。 |
| SC-006 | 1440×1000 桌面及 390×844 窄屏检查；页面无横向溢出，窄屏侧栏选点、坐标修改、顶部保存可操作；图像失败禁用点选且重试恢复。 |
| SC-007 | 19 项逻辑测试、25 个浏览器场景及构建通过；原图来源哈希、固定样本派生和错误注入见 fixtures.json。 |

## 视觉检查

- [α²F 详情](assets/demo-alpha-detail.png)、[α²F 编辑器](assets/demo-alpha-editor.png)。
- [PhDOS 详情](assets/demo-dos-detail.png)、[PhDOS 编辑器](assets/demo-dos-editor.png)。
- [窄屏详情](assets/demo-mobile-detail.png)、[窄屏编辑器](assets/demo-mobile-editor.png)、[窄屏坐标与点表](assets/demo-mobile-inspector.png)。

人工查看上述渲染截图，原图比例保持、编辑入口可见、原图与点可辨认，桌面右侧编辑栏和窄屏上下布局可操作。截图中本机演示身份和材料标签不代表新增业务数据。

## 来源及限制

- [样本来源](assets/fixtures.json)：真实原图与既有 α²F 像素快照匹配；PhDOS 是真实图的固定演示像素取样；图例误识别与低频缺失有明确注入记录。
- [上传图片索引](assets/images.json)：IMG-002 原字节、尺寸与 SHA-256 验证完成；较早 IMG-001 文件缺失，保持未归档状态。
- 初始幅值为相对像素；不采用累计 λ 的刻度作为 α²F 物理幅值。示例积分持续显示不可计算。
- 用户实际试用和视觉认可尚未获得；不能把自动验证记为用户认可。
- 无业务数据修改、无 AI 调用、无数据库迁移、无正式服务部署、无 Git 推送。远程 Spec 双向链接未验证，Issue 保持 OPEN。

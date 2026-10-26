# 图窗平移、适应窗口与零频步骤验收

对应FR-032至036 / SC-022。51项逻辑测试、64个真实Chrome场景及TypeScript/Vite构建通过。

- 已移除选点/平移时的通用拖动提示及其空占位；加点、标定等具体操作指引仍保留。
- 详情和编辑SVG均可右键平移。详情实拖改变viewBox，曲线路径不变；原上下文菜单不干扰手势。
- 工具栏、图例和说明独立布局；fit按实际SVG大小及固定屏幕文字留白计算。DOM实测桌面/390px的全部轴文字与子图均在绘图区内，工具栏/说明位于外侧，当前横轴辅助标签不重叠。
- 按钮倍率由1.35改为1.05；小滚动量微调，大量滚动更快，连续滚动累积；鼠标锚点保持。滚轮帧内合并，视图变化不计算谱数据。
- 零频步骤已写在右侧“零频边界”、quickstart和Overview：选曲线、找到频率0、确认或重标零线、确认已有点或补点、保存看结果；PhDOS逐分波完成。强调在图框内对应位置点击，零频率不要求幅值为0。
- 旧联动、选点、保存、零频检查、旧草稿和异常流程回归通过。用户参数文件哈希仍为 b3c8c9e32bfe0698f80def9171844e26b819e0c50e5e3feaebb62a049311f4e0，未编辑或纳入提交。

证据：[浏览器记录](assets/viewport-browser-validation.json)、[详情](assets/viewport-demo-alpha-detail.png)、[编辑器](assets/viewport-demo-alpha-editor.png)、[窄屏](assets/viewport-demo-mobile-detail.png)。已查看实际截图，标题及刻度可见。用户原图IMG-007/008索引见 [图片清单](assets/images.json)，按原字节归档。

仅修改独立Demo；未改科学点或数据库，未推送，远程Spec链接仍待验证。

# 三邻点与手工调参验收

- 需求：FR-025 / SC-017，默认两侧各3点明显跟随，外侧指数衰减。
- 单一配置入口：demo/src/dragInfluence.ts 顶部 DRAG_INFLUENCE。App 和 engine 共用，避免改参数后说明失配。
- 默认权重：中心1，第1/2/3邻点约0.8667/0.7333/0.6，第4点约0.3639；第16点起低于0.001不再移动，每侧最多15点，含中心共31点。
- 38项逻辑测试通过，包含 edgeWeight/decayLength/minWeight/coreNeighbors 的变更和非法/过大范围保护；TypeScript/Vite构建通过。
- 43个Chrome场景通过，实际拖动核对第3/4/8/15/16点，10000点场景仅31点位移，继续复用准备结果；其他坐标轴、保存恢复、旧数据与窄屏回归通过。
- [机器记录](assets/influence-browser-validation.json)、[界面](assets/influence-demo-dos-editor.png)。

只改变未来拖动的规则，不改已经保存的点；没有数据库操作或部署，未推送。

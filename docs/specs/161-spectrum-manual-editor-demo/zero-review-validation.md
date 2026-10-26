# 保存后零频检查与参数保护验收

## 用户参数

本次开始时用户已修改 dragInfluence.ts 为 coreNeighbors=2、edgeWeight=0.3、decayLength=1、minWeight=0.1。实现期间没有编辑该文件，前后 SHA-256 均为 `b3c8c9e32bfe0698f80def9171844e26b819e0c50e5e3feaebb62a049311f4e0`；该已有未提交修改不纳入本次提交。测试使用此工作区配置，记录在 [浏览器结果](assets/zero-review-browser-validation.json)。

## 功能验证

- 47项逻辑测试通过，含零频缺边界/缺点/候选/完成/失效、多分波及空数据；调参测试分离固定测试用例与运行配置，不再要求重置用户参数。
- TypeScript检查和Vite独立构建通过。
- 52个Chrome场景通过：已有图上标零与补点保存后直接完成；普通0点仍需明确确认；继续核对选中已有候选、确认不改点坐标；保存刷新保持；移点、删点和改标定后不沿用旧通过。
- PhDOS仅H完成时为1/3，La/Sc分别待处理；全部完成后为3/3。390px详情无横向溢出。
- 写入失败保留编辑器，不显示新保存检查结果；近零点不会自动改坐标或被标为已确认。检查只针对位置和选点一致性，不开放科学积分。
- 既有联动、XY移动、连线、识别轴、399点旧草稿副本及存储/图像异常回归通过；无业务API请求或下载事件。

## 视觉与文档

已查看 [α²F完成](assets/zero-review-existing-point-complete.png)、[PhDOS部分完成](assets/zero-review-dos-partial.png) 与 [窄屏全部完成](assets/zero-review-zero-review-mobile.png)，状态、逐分波结果和继续核对入口可见。

[Overview](../../overview/01_Decentralized_Uploading_of_Superconductivity_Data/spectrum-manual-editor-demo.md) 记录调参含义、用户本地比例快照和已实现的保存检查，明确独立Demo未接入正式数据库；根及上传分组导航已连接。

Issue #161 保持OPEN，Spec远程链接待验证，未推送。自动检查通过不代表用户已认可整谱科学准确性。

# 实施任务：研究材料右侧可折叠大纲

输入：[spec.md](spec.md)、[plan.md](plan.md)、[research.md](research.md)、[契约](contracts/ui-and-api.md)。

## 已有实现的独立承接

- [x] T001 保存本项目标原话、来源说明、图片索引和原FR/SC对应，见spec.md与assets/evidence.json。
- [x] T002 [US1] 承接53c32542中plan.md“源代码触点”的本项实现，保留原数据所有权；本轮不重新开发。
- [x] T003 [US1] 承接plan.md“对应用例”和validation.md的既有执行证据及基线失败边界；本轮未重跑业务测试。
- [x] T004 核对本目录全部相对链接、原图/源码哈希、父子关系与FR/SC覆盖，并更新当前功能文档的指向。
- [ ] T005 待单独授权推送后，实际核验远程Spec双向链接；Issue协作状态继续以GitHub为准。

## 依赖与覆盖

FR-001～FR-005、SC-001/002对应T002/T003；SC-003对应T001/T004/T005。
本轮仅技术归档与关系核验，T005不授权自动推送、部署或重做业务验收。后续共享文件修改需串行核对，不能跨子Issue混入需求。

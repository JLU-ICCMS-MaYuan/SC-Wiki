# 数据模型：研究材料右侧可折叠大纲

## 权威对象

状态字段由当前宿主草稿/只读版本提供；state_key是定位身份，#编号只是展示；大纲折叠仅属于界面状态。

## 不变量

PaperMaterialsSection复用materialStateSummary与locateMaterialState；桌面为右侧大纲留宽，来源侧栏位于更高层；按state_key在当前宿主定位，历史无key保留显式位置兼容。

## 迁移与持久化边界

本项沿用现有实体和标准字段，不新增数据库结构或科学键；本轮拆分不更改任何数据。完整原实现及源文件哈希见[证据清单](assets/evidence.json)。

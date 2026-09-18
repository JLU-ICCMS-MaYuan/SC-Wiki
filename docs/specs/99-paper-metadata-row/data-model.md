# 数据模型

## 论文

| 字段 | 语义 | 类型及兼容 |
| --- | --- | --- |
| journal | 期刊名 | 原文本 |
| year | 年份 | 原整数语义 |
| issue_number | 期号 | 新增可空 VARCHAR(100)，无索引与唯一性要求 |
| volume | 卷号 | 原文本 |
| pages | 起始页码输入 | 原文本，兼容已有页码范围及文章编号 |
| doi | DOI | 原校验及唯一性 |

草稿 paper 中 `issue_number` 可省略或为空；解析返回数字期号时归一化为文本。正式论文 Python/Go 模型映射同一列。无新实体、关系或状态转换；待审核/审核生命周期不变。迁移下接 `issue90_data_integrity_repair_v1`，历史记录无需回填。

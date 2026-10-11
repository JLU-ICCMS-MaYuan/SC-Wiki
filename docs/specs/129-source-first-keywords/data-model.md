# 数据模型

## 现有字段

- `paper.keywords_tags: string[]`：当前可编辑关键词，不改变数据库结构。

## 上传草稿新增服务端分析

`keyword_assessment` 为服务端维护的对象：

| 字段 | 类型 | 约束 |
| --- | --- | --- |
| `status` | `completed`、`uncertain`、`failed` | 仅完成时可作为当前值依据 |
| `kind` | `author_list`、`fulltext_synthesis`、`none` | 作者原列与 AI 提炼不混用 |
| `values` | 字符串数组 | 与当前 `paper.keywords_tags` 相等时才可匹配 |
| `evidences` | 原文定位数组 | 文件、页码及逐字引句；作者列表至少一项 |
| `reason` | 简短中文字符串 | 说明来源或失败原因 |
| `source_hash`、`rule_version` | 字符串 | 标识解析来源与规则版本 |
| `covered_batches`、`total_batches` | 整数 | 全文提炼必须相等且大于零 |

用户改写关键词时，分析保留为历史诊断，但不得视作当前值的直接证据。上传转正式论文时，通过已有字段来源结果保留当前版本的来源类别；不新增数据库表。

全文提炼的 `reason` 不再只是“已阅读全部窗口”的过程标记，而是与 `values` 同次模型输出的词语选择说明；`covered_batches/total_batches` 继续单独证明阅读覆盖。没有具体理由时分析不得完成，旧核对理由仅在字段和来源版本仍匹配时可用于侧栏，人工改词后失效。作者原列 `reason` 仍是来源说明，不属于模型推断。

# 关键词来源契约

## 上传草稿

既有 `paper.keywords_tags` 数组保持不变。服务端在 GET 草稿返回只读 `keyword_assessment`；PUT 草稿中的该字段由服务端保存的分析覆盖，不接受客户端自行授予 `author_list` 或 `completed`。人工修改关键词不改写服务端分析值。

## 核对与侧栏

科学字段右侧栏功能设计、原话及历史已迁移至 [#221](../../221-scientific-field-sidebar/spec.md)，本处不再独立维护。

科学字段右侧栏功能设计、原话及历史已迁移至 [#221](../../221-scientific-field-sidebar/spec.md)，本处不再独立维护。

## 全文提炼理由增量

`kind=fulltext_synthesis` 的只读 `keyword_assessment.reason` 应说明当前 `values[]` 如何由本文研究材料、核心现象和方法形成；`evidences[]` 仍提供原文位置，不以理由替代引句。只有覆盖全部有效来源窗口、理由具体、引句可定位且当前值匹配时， 科学字段右侧栏功能设计、原话及历史已迁移至 [#221](../../221-scientific-field-sidebar/spec.md)，本处不再独立维护。
缺理由或仅有“已通读全文”的过程说明时返回待重核，不显示作者原列或原文直接记载。`kind=author_list` 的理由只解释作者栏目来源，不要求编造选择逻辑。

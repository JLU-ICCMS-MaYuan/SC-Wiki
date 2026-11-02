# 数据与所有权

沿用ScientificEvidenceCheck/Source的字段身份、内容/来源版本、状态及依据类型；科学值由工作稿和正式科学表持有。来源存在性由当前snapshot的chunks及不可变来源目录保证。

来源继续使用file_id、chunk_id或chunk_index、block_id、页码及quote。上传到正式文件身份机械映射，chunk身份随正式记录更新，quote原样保存。概括/推断的source_kind、adopted_basis和理由保持。

PaperChunk与PaperEvidence外键表示依据在哪里，不重新证明字段。关系与结果同事务保存，失败整体回滚。无新表、列、标准字段或摘要版本。

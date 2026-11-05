# 审计、备份、演练与精简

从仓库根使用项目Python运行 scripts/compact_paper_storage.py。必须显式指定论文及预期正文SHA；mode默认audit。仅允许本机数据库和文件仓库，本轮不含生产操作。

审计命令：

    python scripts/compact_paper_storage.py --paper-id 1208 --expected-main-sha 5a8f5279732264dc218b9ab865778768e37623127b8bd64bbce6135da101c8da --mode audit

需要新执行时使用新的私有备份目录；同一组参数分别执行mode=backup、rehearse、apply并增加 --backup 指定目录。backup拒绝覆盖目录，rehearse恢复并精简隔离MySQL后删除临时库；apply要求对应成功演练、源数据计划摘要仍匹配以及实际产物可回读。只对已提交且正式冻结的关闭上传正文精简，不清理活动稿。

本轮已完成，不需再次执行apply。备份保留于 .local/storage-compaction/backup-1208/；详细原件见validation.md。恢复材料包含精确数值，不能用普通JSON文本恢复后跳过浮点校验。

必需检查：test:field-contract、test:form-contract、test:form-contract:mutation及build（frontend），新增 test_storage_compaction.py 及交接/来源/存储相邻回归。隔离MySQL测试需使用符合其夹具前缀的临时库，不能把拒绝在业务库运行的保护误报成功。

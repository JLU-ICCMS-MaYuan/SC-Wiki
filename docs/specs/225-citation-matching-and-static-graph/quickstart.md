# 使用与验证

配置既有LLM2目录，不改全站默认。数据库迁移已在隔离库验证，业务环境升级须单独明确执行并核实目标库，再更新对应服务；代码完成不代表已迁移或部署。

经目标环境授权后，本功能迁移的显式目标为 `alembic upgrade 20261106_0225`。仓库已有独立News迁移头，不能用含糊的 `upgrade head` 代替本功能目标；该命令本次未在业务环境执行。

上传正文，在第4步汇总后完成引用匹配，第5步可打开结果新标签页；对照三列和填色，刷新不增加模型调用，其他用户无权读取。隔离提交/批准后新会话重读6条真实内部边。图谱应固定坐标、拖动后停住、增量不重排、刷新恢复默认，空短标题仅搜索/展开时显示。

验证入口：pytest backend/tests/test_citation_matching.py backend/tests/test_citation_matching_lifecycle.py backend/tests/test_citation_graph.py；npm run test:field-contract --prefix frontend；npm run test:form-contract --prefix frontend；npm run test:form-contract:mutation --prefix frontend；npm run build --prefix frontend；Go及浏览器证据由validation.md记录实际结果，不把命令清单当作通过。

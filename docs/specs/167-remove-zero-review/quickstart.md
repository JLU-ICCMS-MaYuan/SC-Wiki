# 验证路径

使用scripts.local_deploy.environment定位Python；pytest使用测试SQLite/JWT。验证无zero字段保存、0.2THz首点直接积分、旧字段失效、无0刻度提取及真实发散错误。
运行正式Vitest和npm build，独立Demo测试和build；确认两处dragInfluence.ts哈希未变。
隔离浏览器通过正式manual/recalculate接口验证首点正频、缺确认、保存继续编辑、自动版本恢复和结果范围；所有API重定向临时SQLite/文件服务，不写业务谱。
实际结果与命令记录到validation.md，本步骤不是已通过声明。

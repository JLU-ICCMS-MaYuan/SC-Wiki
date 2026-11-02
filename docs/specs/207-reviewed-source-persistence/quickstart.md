# 验收方法

1. 新增来源衔接回归，先确认旧实现对定位标记/概括引用失败，再实施。
2. CaH6原稿只读快照，在隔离数据库/事务和临时对象存储调用真实提交入口，保存新论文及来源后重读；不实际送审用户论文。
3. 缺失/错误文件仍拦截；概括不被逐字匹配拒绝。返修和两管理员角色调用真实持久化路径，权限不改。
4. 运行test:field-contract、test:form-contract、test:form-contract:mutation及相关pytest/Go回归。命令、计数和边界写入validation.md。
5. 更新Overview并精确本地提交，不推送；远程Spec链接待验证，Issue保持开放。

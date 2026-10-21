# 验证流程

1. 使用项目Python环境，pytest运行test_review_lifecycle.py及关联核对/建议回归。
2. SCWIKI_CURRENT_MYSQL=1运行test_review_lifecycle_mysql.py，使用现有current_mysql外层事务回滚夹具；不得对用户草稿执行修改测试。
3. 使用本地Vite、Playwright与当前服务函数构造的真实草稿副本执行浏览器脚本；记录页面入口、URL、焦点、滚动位置和请求顺序，明确HTTP适配/身份夹具边界。
4. 只读重新获取目标任务，比较SSCHA/N(EF)保存校验、145项原条件的资格和科学值；浏览器测试中保留真实冲突，不自动批准。
5. 在validation.md记录实际命令、通过/失败、运行版本及未覆盖项。任何失败场景不以“未复现”记为修复通过。

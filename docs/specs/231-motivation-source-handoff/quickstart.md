# 验证入口

本文件是待实施验证步骤，不代表命令已通过。环境为本机原生开发，分支mayuan；不改主线程当前任务或其他工作区改动。

1. 解压assets中的请求/响应，确认首填paper_context为空、窗口有候选、最终没有sources且返回明确上下文不足。
2. 新回归须在原代码先失败，补丁后验证原文全等、编号稳定、合法空值与错误分类。
3. 正式paper_first与motivation调用链覆盖核对、保存/重读、技术失败、人工保护和检查点恢复，不只测独立函数。
4. 使用项目Python运行backend/tests/test_research_motivation.py、backend/tests/test_paper_first.py及受影响既有回归；执行frontend的test:field-contract、test:form-contract、test:form-contract:mutation。
5. 原PDF正文/SI哈希按assets摘要核验，在隔离副本真实重提该字段，保留新响应和引用，不使用旧候选作新的科学答案。
6. 未完成真实模型/网页验收时分别记录，不关闭Issue或宣称Y–H五阶段通过。

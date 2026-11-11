# 默认人工问题窗口接线验证

RagSettings.upload_human_questions_enabled默认true，配置名UPLOAD_HUMAN_QUESTIONS_ENABLED；新任务记录version=1策略。旧无策略任务不自动升级，关闭后已有队列仍可读答。未修改.env或10个Worker上限。

任务DTO只带队列revision、计数和能力；完整题目独立读取。解析动态区域挂载UploadHumanQuestions，按任务/作者/题目/版本隔离临时输入，不展示内部思维链。UploadParsingDetail以task_id保持身份，刷新不卸载编辑器；人工暂停只轮询轻量任务，队列变化才读题目，不重复拉整稿。回答后重读任务，其他标签页答案由轻量轮询发现。等待不计活动耗时，未解问题保留到正常清理，用户取消仍沿原生命周期处理；不静默换模型。

相关后端128项，问题面板/解析动态/论文先行12项交互，四宿主250项、12项变异、字段契约及生产构建通过。独立Redis/RQ/HTTP/SQL证据见[#239验收](../239-field-human-question-queue/validation.md)。原PDF新模型相关字段已执行；LaH9首次未产生问题，按事实记录。

真实新文献完整问题链及Y-H五阶段仍待网页验收；不以代码、ready或隔离测试替代。未推送或部署其他环境，远程Spec门仍未完成。

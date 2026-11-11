# 人工问题、答案与局部恢复数据模型

## 唯一所有权

当前科学值仍在既有草稿，人工材料在ScientificManualEvidence/来源共享链，合法审核决定仍为field-review-v2。问题是运行元数据，拟以现有ScientificUploadDraft.state的human_questions子对象持久保存，Redis和解析制品只作缓存/恢复镜像，不增加数据库表、标准科学字段或独立当前值。

首题出现时若不存在ScientificUploadDraft，先用同task_id/owner_id持久保存现有任务状态及可恢复部分稿，再提交问题。空的材料列表不表示解析完整，也不创建正式papers。SQL提交失败不能响应已保存。已有工作稿读取仍遵守authoritative_state，不让后续persist_upload以旧state覆盖刚接受答案。

## 主要实体

| 实体 | 最小内容 | 约束 |
| --- | --- | --- |
| QuestionQueue | version、revision、按创建顺序排列的问题 | 队列为本任务所有；并发写须比较revision，镜像不能反向覆盖SQL |
| Question | question_id、logical_key、prompt_revision、kind、title、source_refs、targets、options、state | logical_key由冲突身份和来源关系组成；不能只按字段或理由文字去重 |
| TargetRef | task/输入身份、candidate/reading或state/module/record/item_key、内容/来源/适用范围版本 | 可含多个真实依赖，不凭数组下标推定目标；绑定缺失须明确，不静默丢弃 |
| Answer | answer_id、question_id、prompt_revision、choice_id或人工文字/理由、actor、时间、处理状态 | 同一答案重试幂等；已接受方向不因网络回执丢失而再次执行 |
| WorkProgress | 稳定对象/字段、输入签名、completed或waiting_human、question_refs | 不能只保存连续完成组；已完成项不被等待项覆盖 |

Question.options至少提供推荐、查证、人工填写三个入口；推荐排首位。暂不处理是不提交答案的操作，不能存成推荐或弃题。

## 状态语义

- waiting：尚需人答；不点击、稍后处理、刷新都保持。
- investigating：用户要求进一步查证，原问题保留，只按现有预算查询相关资料；没有进展不得不断发新题。
- answer_received：答案已持久提交，但尚未应用/补做，不冒充解决或审核通过。
- resuming：同任务合法执行正在按答案处理相关字段。
- resolved：原问题所需处理已经成功保存；这不是字段科学审核通过，审核仍按#220/#221。
- stale：问题、目标或来源真实变化，旧回答不能应用；保留当前恢复所需信息与用户输入，新题或重新确认明确版本。

有效新决定替代旧决定后以当前采用方向为准；必要旧来源反证保留。运行中的未解决问题和恢复资料不丢；不把每次输入和模型中间回答永久累积为字段历史，正式交接沿#192快照。

## 事务与恢复

同一任务沿原锁和SQL事务串行写问题/答案/版本，模型调用放在事务外。运行中仅保存答案并在安全点消费；空闲待答任务通过正常RQ排队恢复，只有一个执行可领取。任务执行代次隔离旧Worker；人工问题绑定输入/字段/来源版本，不因正常暂停续跑增加代次就自动过期。

任务只剩待答时复用paused，pause_reason为human_questions；在检查点保存工具回执、原图定位、模型引用、局部进度后释放Worker，不将人工等待冻结成ready。等待不计活动模型处理耗时；保留到用户正常清理，计入原100任务上限。不存在有效模型引用时明确报告恢复阻塞，不静默换模型或把旧答案冒充新提取。

服务重启从持久state和局部检查点恢复；文件镜像落后可从SQL重建，队列先提交后恢复失败时答案仍为answer_received且可幂等继续。草稿写入成功而完成标记失败时，恢复先核验已应用目标/答案标识，再决定是否补做，不能重复应用。

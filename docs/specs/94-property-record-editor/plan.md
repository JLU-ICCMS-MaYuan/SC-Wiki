# 实施计划

输入：[Spec](spec.md)、[Research](research.md)、[数据](data-model.md)、[契约](contracts/record-form.md)。

## 技术上下文与职责

React 19 / TypeScript 5.6 / MUI 的 PropertyModuleEditor 负责菜单、定义选择和记录折叠；
SchemaDrivenRecordForm 负责实验条件单框和旧对象的可读投影。Python upload_jobs 的分段及汇总 prompt
负责逐条提取；现有 convert_legacy_state 已支持 Tc 条目级 experimental_conditions，归一化后进入
property_modules。后端 property_modules.validate_record 与前端 validateRecordClient 校验 description 类型。
MySQL 持久化仍使用 payload_json；测试以 SQLite 执行真实写读。

## 质量门

| 来源 | 要求 | 实现方式 |
| --- | --- | --- |
| AGENTS.md | Spec 先行、中文文档、明确提交范围 | 本目录先形成全部文档，再实现并验证 |
| #90 当前事实 | 条件属于记录、定义不可原地修改 | 使用已有开放对象内 description，不改已发布定义 |
| 用户 | 六方向弱约束、单框、记录折叠 | 两阶段 prompt + 共享输入与 Accordion |
| KISS / DRY / YAGNI | 控制复杂度 | 共用组件实现，不增加接口、数据库迁移或依赖 |

## 需求与验证映射

| 来源 | 设计与数据来源 | 任务 | 验证 |
| --- | --- | --- | --- |
| FR-001 / US1 / SC-001 | definitionLabel 只输出类型和方法 | T002 | 菜单、标题、只读标签、提交版本断言 |
| FR-002、004 / US2 / SC-002 | 单框读取本条 description；旧字段无损保留 | T003 | 旧数据、换行、复制、编辑、只读测试 |
| FR-003、004 / US2 / SC-002 | CHUNK/SUMMARY prompt → normalize → persist | T004 | 模拟 LLM 返回，执行真实下游转换和数据库写读；核对真实调用的 prompt |
| FR-005、006 / US3 / SC-003 | Accordion 用 module/record 稳定键维护交互 | T005 | 多条记录独立切换、键盘、复制删除及错误摘要 |
| 全部 | 文档与完整回归 | T006 | [快速验收](quickstart.md) |

## 阶段与依赖

T001 文档门通过后先写定向行为测试，再执行 T002～T005；同文件改动串行，T006 最后验证和回写。
没有新存储和外部服务依赖，不需要数据迁移。旧对象投影只限实验条件显示边界，不扩散到正常数据库查询。

## Tc 紧凑布局增量

SchemaDrivenRecordForm 将 Tc 核心行交给 TcRecordFields，不再渲染原始记录。
使用容器查询实现 400/640px 断点，避免按窗口宽度判断窄卡片。普通物性保持原表单。
TcNumber 保留本地输入文本，完整合法值写入规范数值，清空或临时非法输入写入 null，
避免后台继续接收旧值；本组件发出的更新不重置输入文本。
propertyModules 统一生成当前 Tc 的兼容 value_raw/unit_raw，在表单加载、编辑及应用核对建议时同步，
不自动从 raw 反推已清空的值。后端 validate_record 对有效 Tc 同步兼容字段后计算校验和，
覆盖上传、管理员、导入及核对建议的保存通路。evidence_proposals 的 expected_claim 使用同一
后端转换规则，核对候选不再编辑派生的 raw/单位，避免保存后精确内容确认失败。
数值和范围使用 K，文本和布尔不保留旧单位。
此规则仅在传入记录的归一化/保存过程中应用，不批量更新数据库或抹除审计历史。
共享校验在上传草稿保存及管理员两段保存之前阻止无效 Tc；现有提交校验复用同一规则。
PropertyModuleEditor 的 Tc 摘要直接读取规范值，字段锚点及 record_key 不变。

| 来源 | 实现与事实来源 | 任务 | 验证 |
| --- | --- | --- | --- |
| FR-007、008 / SC-004 | TcRecordFields、共享记录表单 | T007、T008、T012 | 浏览器容器宽度与单入口断言 |
| FR-009、010 / SC-005 | 本地输入文本、现有规范值列、共享校验 | T007、T009 | 用户输入、保存请求和持久化往返 |
| FR-011 / SC-006 | 字段锚点、稳定记录键、现有核对工作流 | T010、T011 | 管理端/上传/只读回归与生产构建 |

依次完成文档、行为回归、组件和保存校验、浏览器及后端验证、总览与 Issue 回写。

用户最新澄清对应 T012～T014：先将旧保留原始值测试改为覆盖当前值的失败测试，再实施
前端单入口、前后端同步和核对兼容，最后保存往返、文档回写与独立提交检查。

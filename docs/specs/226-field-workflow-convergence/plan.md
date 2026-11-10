# 实施计划

## 现状、根因及职责

- 只有ScientificFieldBox、ReviewPaperTextField接管配置事件；普通题录、分类、材料字段、方法及普通物性仍退回只读。新增统一按类型分派的设置表单，复用现有值更新回调和原字段类型；原已接入控件优先，不造第二份正式值。
- currentEvidenceField中目录对象与服务端名称列表表示不一致；统一科学比较/人工资料身份，界面编辑器可保留目录条目。local_modified与人工区共用实际值变化，保留技术错误优先及无关字段隔离。
- 扩展field-review-v2的without_evidence模式，绑定值、来源、范围及当前人工资料状态；零资料有效决定使字段可提交并warning。reason+真实证据保存后旧决定失效。Go转存、快照、正式出处、公开读取均透传，不把warning当阻断。
- 正常提交的已改字段必须真实reason+items；旧缺证原因不能替代新常规证据。未改同版本有效结论复用；旧empty决定保持有界兼容，新的明确零资料按钮覆盖空/非空。
- 链接证据增加url类型，保存地址，显式核对时读取公开网页或PDF。限制协议/公网目标、逐跳重验、时间/体积，记录失败；不为保存调用模型。文字一个框，旧TXT/MD与历史证据保留读兼容。
- 写事务共用同一SQL会话，paper→work→review/revision→manual/check；读取权限只读小元数据。后台persist_completed_results复用snapshot_for的现有会话，去掉自阻塞；数据库异常独立分类。当前权限/版本内重验保持，外部模型在事务外。

## FR/SC→设计→任务→证据

| 来源 | 模块 | 任务 | 验证 |
| --- | --- | --- | --- |
| FR-001/SC-001 | 字段统一表示、ReviewFieldSettings和四宿主 | T002/T005 | 全字段接入、应用/取消/保存及列表改值 |
| FR-002/SC-001/003 | field_decisions/field_review/状态/Go/快照 | T003/T006 | 当前黄决定、普通改值/补证/转接/公开搜索 |
| FR-003/SC-003 | manual_evidence、人工区、model_review | T004/T006 | 混合输入、10项边界、真实读取/失败 |
| FR-004/SC-002 | workdrafts/field_drafts/snapshot_for/worker | T002 | 先失败、真实并发及同会话 |
| FR-005/SC-005 | 正式Chrome/API/RQ/批准/搜索 | T008 | 用户指定实际1208黑盒回执 |

先建档和失败回归，再依次事务、决定与资料、统一字段界面和颜色、必需检查、隔离反例和正式黑盒。已确认现有基础规则，修复时不为通过放宽校验；并发#224/#225文件不混入提交。

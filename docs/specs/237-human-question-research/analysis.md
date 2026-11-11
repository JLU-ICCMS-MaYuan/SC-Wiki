# 四目标建档与跨Spec一致性检查

## 范围映射

保留四目标、13个小目标，2＋3＋5＋3。目标一为type:documentation，其编号目录保存调研交付规格，不冒称运行Feature；目标二至四为type:feature。全部复用现有上传Epic #24，没有另建第五个目标或新Epic。

| 小目标 | 唯一负责Issue | 需求与设计 |
| --- | --- | --- |
| 1.1 Codex机制 | #237 | [规格](../237-human-question-research/spec.md)、[计划](../237-human-question-research/plan.md) |
| 1.2 开源取舍 | #237 | [规格](../237-human-question-research/spec.md)、[计划](../237-human-question-research/plan.md) |
| 2.1 解析范围 | #238 | [规格](../238-research-scope-human-routing/spec.md)、[计划](../238-research-scope-human-routing/plan.md) |
| 2.2 问题识别 | #238 | [规格](../238-research-scope-human-routing/spec.md)、[计划](../238-research-scope-human-routing/plan.md) |
| 2.3 操作边界 | #238 | [规格](../238-research-scope-human-routing/spec.md)、[计划](../238-research-scope-human-routing/plan.md) |
| 3.1 问题队列 | #239 | [规格](../239-field-human-question-queue/spec.md)、[计划](../239-field-human-question-queue/plan.md) |
| 3.2 暂挂与继续 | #239 | [规格](../239-field-human-question-queue/spec.md)、[计划](../239-field-human-question-queue/plan.md) |
| 3.3 选项交互 | #239 | [规格](../239-field-human-question-queue/spec.md)、[计划](../239-field-human-question-queue/plan.md) |
| 3.4 答案与证据 | #239 | [规格](../239-field-human-question-queue/spec.md)、[计划](../239-field-human-question-queue/plan.md) |
| 3.5 局部恢复 | #239 | [规格](../239-field-human-question-queue/spec.md)、[计划](../239-field-human-question-queue/plan.md) |
| 4.1 模块接入 | #240 | [规格](../240-human-question-default-integration/spec.md)、[计划](../240-human-question-default-integration/plan.md) |
| 4.2 功能开关 | #240 | [规格](../240-human-question-default-integration/spec.md)、[计划](../240-human-question-default-integration/plan.md) |
| 4.3 验证与使用 | #240 | [规格](../240-human-question-default-integration/spec.md)、[计划](../240-human-question-default-integration/plan.md) |

## 依赖图

```mermaid
flowchart LR
 A["目标一 #237：调研依据"] --> B["目标二 #238：本文范围与问题识别"]
 B --> C["目标三 #239：队列、暂挂及局部恢复"]
 C --> D["目标四 #240：默认开启与正式接入"]
```

依赖无环。图片复用目标三归档是文档链接，不是调研运行依赖；#237不需要等待#239代码完成。创建文档不表示上游实现已满足，下游实施前按对应契约检查。

## 需求、职责与旧要求

- #237只拥有公开证据和开源取舍，不选装Agent框架。Codex固定5228d94源码；其余main/master可漂移且不冒充本项目实测。
- #238只拥有本文对象/结构收录与科学问题路由；#188的先补读自纠沿用。#211/#227的仅范围Tc排除结构条款按新要求登记为待替代，运行代码尚未变化；Tc界限不变具体点。
- #239唯一拥有问题/答案和局部进度模型、读答接口及可复用UI组件；#240引用这些协议，不另造状态或字段当前值。
- #240拥有默认开关、公开能力和正式宿主接线；已有待答任务关闭后可处理，默认新文献使用，不安排真实重复解析对照。
- #220颜色、#221侧栏/资料/审核、#192快照、#203标准字段及#224技术错误重试继续各自拥有规则。已回答/处理成功与科学supported、人工approve、论文approved分开。
- 用户方向可以作为人工依据，不伪装论文原文；先保存方向不代表直接生成审核资格，也不要求模型替用户重复裁定。

## 共享改动顺序

| 路径 | 先后归属 | 冲突处理 |
| --- | --- | --- |
| backend/ingest/upload_jobs.py | #238路由接线→#239安全点→#240正式状态 | 同一文件串行，保留无关共享改动 |
| backend/ingest/model_review.py | #238问题事实→#239局部human_context | 不新增独立分类模型或全稿核对 |
| backend/ingest/upload_tasks.py、scientific_evidence.py | #239持久/幂等→#240能力/恢复 | 统一SQL提交与缓存顺序，不存在两个权威队列 |
| material_batches.py、model_runtime.py | #239局部检查点与等待→#240集成验证 | 技术失败停止规则不因科学待答放宽 |
| UploadModelActivity/UploadPage | #240正式挂载#239组件 | 不重建整表、不引入另一份科学current_value |

## 覆盖检查

FR/SC至任务与验证映射分别在各plan.md，引用任务均存在。目标二先验证旧仅范围排除反例，目标三验证局部等待与首题持久化反例，目标四验证默认及正式宿主。必要三项契约、四宿主、真实PDF受影响字段与新文献业务验收分别列入，不以README、文件存在、夹具或代码静态断言冒充运行通过。

已对照完整用户初始需求和后续结构范围、默认开启、四目标及建档授权：保留全部原话，AI方案另列；三个入口、等待不丢、其他字段继续、人工证据、仅表单动作与低耦合均有对应FR。未把“进一步查证”做成无限重试或新常设审核轮次。

## 当前文档门边界

本轮完成Issue及本地技术草案建档；用户已认可方案，但本文新增接口和实体细节未逐字审阅，完整工程草案确认项保留未勾选。Spec远程文件未推送和核验，双向远程链接项未完成。两项不以创建文件/本地commit消除，不宣称已具备实施文档门或业务交付条件。

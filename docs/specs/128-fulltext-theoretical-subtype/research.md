# 技术决策

## R1：独立全文分类而非沿用候选汇总值

**决策**：全文汇总继续生成论文其他字段，但 `theoretical_subtype` 由后续专门 LLM 判断覆盖。短文直接输入全部有效文本，超长来源先逐组提炼贡献，再综合所有组。

**理由**：当前汇总只看到分段候选 JSON，无法保证分类模型通读原文。固定前缀或仅 Methods 会重复截图中的问题。

**备选方案**：直接沿用候选汇总值或固定截取正文前缀；都可能漏掉后文的主要结果和讨论，故未采用。

**证据**：`backend/ingest/upload_jobs.py` 在汇总后调用 `classify`；`tests/01_decentralized_uploading/test_fulltext_theoretical_subtype.py` 覆盖多批次，真实 H3S 结果见 [quickstart.md](quickstart.md)。

## R2：归纳与逐字事实分开

**决策**：核对记录对该字段采用 `paper_synthesis` 来源类别，理由及可定位支撑段落共同构成资格；只有方法段落不能授予支持。

**理由**：分类不是论文逐字写出的枚举，但可由全文证据充分支持；保留现有原文、人工记录、AI 理由顺序。

**备选方案**：沿用 `paper_quote` 和通用“无需推断”文案；会把分类冒充原文直接陈述，故未采用。

**证据**：`backend/ingest/property_evidence.py` 校验贡献段落，`frontend/src/components/EvidenceWorkflow.tsx` 显示专用提示；相关组件与浏览器夹具覆盖来源文案。

## R3：只使单字段旧核对过期

**决策**：分类分析加入该字段的内容/来源身份；规则升级不使其他字段全量过期。重跑在原任务锁下比较 AI 初始值与当前值，失败不沿用旧 AI 判断。

**理由**：H3S 已有大量其他字段核对，整体规则升版会造成无关重查及用户修改风险。

**备选方案**：接受客户端回传分析、提升全局规则版本或覆盖整份草稿；分别存在伪造、无关失效和覆盖人工编辑问题，故未采用。

**证据**：`backend/api/rag.py` 保持服务端分析所有权；`backend/ingest/scientific_evidence.py` 构建字段身份；定向重跑和单字段哈希测试见 [quickstart.md](quickstart.md)。

## R4：沿用正式来源结构

**决策**：正式分类仍存现有论文列，提交时把上传核对归因与引句重定位到正式来源；不新增业务列或公开提交路由。

**理由**：分类与审核来源已有身份和历史机制，复用可避免迁移及双写。

**备选方案**：新建专用分类表；当前仅一个字段，会增加同步与回滚负担，故未采用。

**证据与边界**：`backend/ingest/scientific_evidence.py` 的转接测试已通过；真实提交、审核后的完整持久化仍需隔离端到端验收，详见 [quickstart.md](quickstart.md)。

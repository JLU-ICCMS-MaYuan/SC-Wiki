# 需求质量检查表：独立登录页

**日期**：2026-10-22。检查需求文本，不以此代替实现测试。

- [x] CHK001 目标与阶段边界完整。[FR-001/009、US1～3；对照用户批准原文，第一阶段独立 Demo，第二阶段待视觉评审]
- [x] CHK002 视觉与动画可验收。[FR-002～004、SC-001/002；规定白底、分栏、尺寸、约 16 秒周期及暂停]
- [x] CHK003 认证与失败恢复边界一致。[FR-005/006、data-model、contracts/demo-auth；模拟账户与生产服务隔离，含错误、过期、冷却]
- [x] CHK004 初始需求与后续选择、批准方案完整保留。[spec.md 原始需求记录及 approved-request.md；逐段核对用户描述与完整实施消息，AI 整理与原文分开]
- [x] CHK005 高影响问题已逐项处理。[spec.md 澄清记录；用户选择极简、统一入口、安静循环、SVG，并完整要求实施方案；正式接入仍未授权]
- [x] CHK006 Spec 模板已逐栏核对。[spec.md 含目标、故事、边界、FR、SC、实体、依赖、范围外、澄清、附件和确认；实体仅为内存态，无数据库迁移]
- [x] CHK007 实施基线获用户明确批准。[approved-request.md 保存用户完整引用的方案及 PLEASE IMPLEMENT THIS PLAN；Spec 仅结构化该方案，不把未见 Demo 记为已批准]
- [ ] CHK008 Issue 到远程 Spec 的链接有效。[仅本地提交，远程链接待验证；spec.md 指回 #151，GitHub 查询确认标题及唯一 type:feature；不自行推送]
- [x] CHK009 两张上传原图均归档。[spec.md 的 IMG-000/001，assets/original-login-entry-first.png 与 original-login-entry.png；分别复制并核对 PNG 尺寸和 SHA256，两个文件哈希不同]
- [x] CHK010 与原文逐项检查遗漏和偏离。[plan.md FR/SC → 设计 → 任务 → 验证映射；生产集成没有混入 Demo 完成结果]
- [x] CHK011 后续选择保留且说明取舍。[spec.md 保留四项用户原文答复；SVG 例外和所有入口统一仅第二阶段实施均与批准方案一致]

远程链接未核验、用户视觉未验收和第二阶段未实施仍阻止 Feature 关闭，不阻止交付本地 Demo。实现证据见 quickstart.md 与 design-qa.md。

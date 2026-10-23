# 正式谱详情与历史读取合同

## 现有列表的附加字段

GET /api/rag/spectra?target=upload|paper|revision&target_id=...
每个 item 增加 recorded_at（当前运行创建时间）、recorded_state_key、recorded_caption、historical。旧字段保留，数据库无迁移。每个集合仍保留自身当前运行；材料状态页面按谱类型聚合一个入口，在各集合当前运行中优先有曲线者，再按时间和 ID 排序。这是展示规则，不改变采纳或覆盖存储值。

## 历史

- GET /api/rag/spectra/{collection_id}/history：沿目标权限查询，返回 items，含 id、status、current、created_at、state_key、caption。
- GET /api/rag/spectra/{collection_id}/runs/{run_id}：返回完整历史 item，必须属于当前目标与集合。历史标为 stale、review 为空；同条件比较不可复用。
- GET /api/rag/spectra/{collection_id}/export?...&format=json|csv&run_id=...：可显式导出私有历史，沿相同权限和归属校验。
- 无权读取目标或公开用户读取未审查历史返回 403；不存在/跨集合运行、跨目标或论文 revision 不符返回 404。不提供历史写入/删除接口。
- 原图通过已有 image 接口读取集合不变的来源，历史不替换图片。

## 新提取与数学质量

算法标识 spectra-production-v3。PanelCalibration 保留 panel_id 作为显示标记；持久集合 panel_key 由材料状态、曲线 kind/projection 构成稳定摘要，同来源微调频段或改名不再新建相同身份。

CurveCalibration 增加可空 amplitude_evidence（α²F 独立幅值依据）。无该依据不输出物理 α²F 积分。要求 frequency_ticks 内唯一明确零刻度；约束零点拟合、残差不超过一个像素。ROI 扩展到图内真实零频像素，亚像素通过原图像素插值取色。零频颜色不可辨则 observed/reconstructed 均保持 null，status=missing，运行 needs_review。覆盖报告含 zero_frequency_observed；不读取论文 λ 反推幅值。

quality.dos_mode_integral 在原胞和完整绝对密度条件满足时含 integral、primitive_atoms、target_modes、absolute_difference、relative_difference_pct、frequency_interval_thz、structure_evidence；否则 status=unavailable 与 reason，不输出伪数值。部分公开 DOS 不能返回整个原始集合的总积分。

## 页面

新标签链接包含 target、target_id、state_key、collection_version、run、curve 和 kind。不调用保存接口，详情使用已保存的材料条件。旧地址兼容 curve 推断 kind；版本变化提供打开最新结果。历史切换仅内存读取，异步请求过期时不覆盖新选择。

相同输入摘要下已有数值的 succeeded/needs_review 运行不可被重试改写；复用原运行。更改标定、状态依赖或算法版本才生成新数值运行。无曲线的失败/发现记录沿既有重试机制处理。

## 子图显示框扩展

CurveCalibration 可提供 display_bbox（原图绝对像素四元组，或 null），必须包含 roi 并位于原图内。提取输出保留该字段，但不平移或重写点坐标；新增字段本身不改变谱数学。旧记录缺字段时前端在 ROI 邻域检测图框，可信边框和合理显示框用于 viewBox/clipPath；过大的模型框不直接采用，无法独立定位时明确提示。

## v4 颜色补读与歧义来源

宽松补读需严格本色或纯净暗色邻域支持，不取不相连候选的整体均值。歧义行不允许插值跨越；点保留 rejected_chromatic_pixels、candidate_components、reconstruction_blocked，CSV 同步导出。detection_mode 可为 ambiguous_components 或 unsupported_chromatic，status 仍为 missing；页面据此显示待核对原因。校验版本 spectra-production-v4 保证旧输入不会复用旧错误算法结果，旧运行数值不覆盖。

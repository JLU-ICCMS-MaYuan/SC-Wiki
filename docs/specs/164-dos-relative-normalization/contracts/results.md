# 接口与页面契约

复用 POST /api/rag/spectra/{collection_id}/recalculate，kind=phonon_dos；版本、身份和状态校验不变。失败计算以分层 status/reason 保存到新运行；请求鉴权/版本冲突仍是现有 HTTP 错误。
只新增 JSON 派生字段（见 data-model.md）；旧 dos_mode_integral 保持兼容。初次提取同样调用计算器。未知旧结果提示重新计算。
03 展示逐元素面积与范围、实测/预期占比、按 3N 归一化结果和原始绝对积分；缺条件显示原因，不列内部 JSON。02 可以在有效共同候选存在时切换相对像素/按 3N 密度刻度，只改展示不写数据。历史、失效及限定频段不得显示当前完整归一化。
频率统一 THz，模式密度为 modes/THz/primitive_cell；绝对输入的单位转换沿用提取和人工保存规范。公开数据依赖全部分波的计算必须先检查可见性。

元素比展示读取 shares.element_ratio，以参考元素=1显示面积估计/当前化学式比例和最大占比差（百分点）；没有化学式时标明结构参考。删除 shares.coverage_note 展示和频段确认失败原因。dos-relative-v1 报告显示重新计算提示，不沿用旧 reason；v2 继续展示有效独立结果。

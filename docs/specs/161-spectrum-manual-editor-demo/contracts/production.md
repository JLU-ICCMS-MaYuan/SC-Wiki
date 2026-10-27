# 人工修订正式接口契约

## 读取编辑文档

`GET /api/rag/spectra/{collection_id}/manual`

参数：`target`、`target_id`、`kind=alpha2f|phonon_dos`、`collection_version`、`run_id`。

沿用登录和谱目标权限。只允许当前材料状态下的最新集合/运行；历史、来源失效、材料变更或未归属返回409。无权403，不存在404。返回 `documents`、`version`、`collection_version`、`base_run_id`。每条文档对应一条曲线，保留各自标定；原图地址由前端既有鉴权下载生成，不能从文档任意换图。

## 保存修订

`POST /api/rag/spectra/{collection_id}/manual`

请求字段：`target`、`target_id`、`expected_version`、`expected_collection_version`、`base_run_id`、`document`。正文文档最多4MB、每条曲线最多20000点、最多5000条操作记录。点ID须唯一，像素在来源图框内，标定非退化且有限，频率支持THz、cm-1、meV；物理幅值改标定需填写依据。

服务端取得集合锁并核对目标、集合和基础运行版本。校验失败422、版本变化409、无权403；错误不创建新运行。成功创建新的 `SpectrumRun`，保留父运行和作者，更新 `current_run_id` 与集合版本，撤回旧采纳。返回最新谱列表；前端只在成功响应后更新详情与地址中的run/版本。

## 数据与科学边界

- `manual_documents` 保存编辑像素、描线顺序、标定、显式零频记录及操作；`manual_provenance` 保存服务端作者、时间和父运行。返修复制后编辑文档重新绑定新集合身份，坐标不变。
- 点数值由服务端按像素和标定换算，频率统一THz。人工调整不伪装为原始自动观测；原运行不修改。
- 旧积分、比较和候选失效。人工描线允许频率回退/重复作为待核对结果保存，但不能直接采纳为单值谱；不自动计算λ/ωlog或3N。
- 零频检查由服务端生成，普通0点没有显式确认仍待核对。多个PhDOS分波按各自运行记录检查。
- 公开读取继续按采纳状态和限定频段过滤，并移除内部编辑文档及操作作者信息。CSV保持既有鉴权，补充点身份、像素、断边、人工状态及父运行字段。
- 本轮无数据库表变更、无迁移、无模型调用或重提取。保存新版本是用户点击触发，代码接入过程不批量修改业务数据。

## 连续描线前驱

可选point.connectTo为同曲线较早点的ID。正式存储校验前驱合法；像素数值和显式边都保留。被删除或被公开频段过滤掉的父点不能留下悬空引用或偷偷改连邻点。普通双击仅结束前端追加，不产生保存API请求。

## 末端吸附

可选point.joinTo为同曲线存在且非自身的ID，允许引用早于或晚于尾点的已有目标；不改变connectTo前驱。保存前校验，不复制目标点。数值曲线及CSV同时保留join_to；公开裁剪删除不可见目标引用。仅正式页面生效，双击只结束工作副本描线，保存调整才入库。


## 主动重算
POST /api/rag/spectra/{collection_id}/recalculate：target、target_id、expected_version、expected_collection_version、base_run_id、kind(alpha2f/phonon_dos)。客户端不得提交积分数值。返回完整listing及新版本；科学条件不足作为200中的unavailable及具体原因，权限403、旧版本409；失败不覆盖原记录。仅同步数值积分，不读取图像/调用AI。
quality.integrals.raw新增parameters.lambda/omega_log独立status/value/reason，兼容lambda_integral/omega_log_k；DOS积分status与comparison_status独立。quality.recalculations[kind]包含base_run_id/calculated_at/author_id/algorithm_version。历史数据按旧显示条件兼容。

## 拓扑诊断
重算响应quality.trace_diagnostics[kind]含curves列表，每项curve_id/name/component_count/point_count/issues。issue包含kind/message/points，points含point_id/frequency_thz/amplitude/x/y，像素不可确定时为null。问题类型disconnected/isolated/cycle/branch/invalid。诊断属于返回的新run，编辑保存后失效；公开接口移除。无新写入接口。


## 显式重新核对材料条件

POST /api/rag/spectra/{id}/revalidate：target/target_id/expected_version/expected_collection_version/base_run_id/kind/state_key/confirmed:true。仅同来源、当前存在的同state_key允许重新确认；不接受点/标定/新材料身份替换。不满足前提409/403/422；成功返回listing和新run。确认说明：沿用当前谱到当前已保存材料条件，不等于科学采纳。
listing的stale_reasons为historical/source_changed/state_missing/state_changed数组，只读展示。内部state_revalidation不公开。


## 真实高频末端与预检查

manual文档highEndpoint可选/null：pointId、x、y、frequencyTHz、evidence。保存时须指向当前最高频点并匹配坐标/THz；依据不得空白。修改导致失效时清空证据，不移动点。缺省旧文档保持未确认。
trace_diagnostics问题增加high_endpoint/low_endpoint/zero_confirmation/nonzero_zero/negative_amplitude/negative_frequency/nonfinite_sample/duplicate_frequency/frequency_backtrack；高端meta包含actual_thz/frame_thz/difference_thz/difference_px/reference_pixel，points仅含实际点，不伪造目标幅值。
quality.automatic_repairs[kind]记录本次精确断端连接的曲线/点ID与位置；人工文档写入auto-connect-exact-endpoints操作，源run保持。公开过滤移除内部操作报告，后台参考与时间继续保留。

撤销自动连接以undo-auto-connect操作记录端点ID；再次重算不重新加入同一对连接。DOS的component_intervals记录各分波独立且已核对的实际积分范围；未全部核对时发projection_range定位项，不通过补零对齐。

## 已取消高频末端核对
highEndpoint已废弃，GET manual不提供，POST manual忽略旧客户端此字段，不校验其中内容；历史存档不改。重算不执行high_endpoint/projection_range检查，不读取末端确认。α²F最高频点和DOS各分波自身最高频点直接作为各自积分上限。此前末端证据/差距规则全部由本条取代。

## 已有线段插入
沿用manual点契约；插入更新局部前驱/断边/吸附关系，不新增字段。正常邻边插入保存为A—N1—N2—B，原A—B边删除，新增点ID保留，其他边不变。点数组可为满足既有connectTo前驱顺序而插入到原边较后端点前；数值和ID不因重排改变。操作kind=insert-chain保留起点/终点和新增点数。

## 普通查看版本URL

身份通过时，普通详情使用GET列表的当前item；URL中的run/collection_version仅同步为最新值，自动replace导航，无业务写请求。错误target/集合/材料/curve不得通过自动导航绕过。显式历史及编辑/请求进行中暂停自动导航。保存/重算仍携带打开时各级版本并由后端核验；本轮无后端契约变化。

## 保存并继续编辑

manual接口保持逐曲线保存。前端onSave返回更新后的编辑文档列表，并同步editorInput的新内容版本、集合版本和run。弹窗按用户意图区分保存切换与保存返回，成功后才切换；保存失败留在当前曲线，不重复提交。已保存文档成为该元素下一次进入的基线，其他文档保持已验证的来源和身份。

连续编辑时详情的只读listing和原图URL保持原快照，关闭编辑器时应用最近成功响应。实际数据库写入在每次POST完成时已生效；刷新普通详情会按既有规则获取最新结果。


## 已取消人工零频核对（#167）

此前显式零频记录、服务端零频检查和low_endpoint/zero_confirmation/nonzero_zero诊断规则由[新契约](../../167-remove-zero-review/contracts/behavior.md)取代。GET/POST manual不再生成或要求zero，旧zero在输入/读取边界忽略。首点允许大于0，按已有采样区间计算，不自动补点；真实f=0且α²F非零的数学发散继续报告。通用标定与幅值零基线保持。此前物理幅值依据的非空要求也已由#163取消。

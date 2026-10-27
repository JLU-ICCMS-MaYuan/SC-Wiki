# 预检查、可靠自动修复与真实末端验收

日期：2026-10-27。用户确认润色后的六项需求：“对，这这个需求去做事。”对应FR-062至065、SC-035至037。

## 本轮改变

- 先统一检查再提供人工定位。除拓扑外，检查频率回折/重复、负频率/负幅值、非有限样本、零频覆盖/确认/非零幅值、高频末端及DOS分波范围。可定位项提供稳定点ID和原图坐标；不以首个失败掩盖其他问题。
- 图框高频上限只是参考。当前最高频点低于图框时，显示实际末端、参考上限、频率/像素差距；允许用户填写原图依据确认该点是真实截止，积分上限采用实际点，不插值/补点/强制末端幅值为零。
- 末端证据包含pointId/x/y/frequencyTHz/evidence，源图与身份仍由正式保存契约校验。删点、移点、增加更高频点或改频率标定使确认失效；确认及撤销/重做使用既有编辑历史。
- 自动修复仅处理人工文档中像素/频率/幅值完全一致、唯一配对且能形成连续单值路径的开放断端，补记joinTo，保留全部点。按位置/数值哈希和片段并查集处理，不做全点两两距离比较；操作数量和文档尺寸受限。
- 自动连接写入新run及操作记录，可定位检查和显式撤销；保存撤销后再次重算跳过被撤销的端点对。仅显式相连且源像素/数值完全重复的相邻样本在积分副本折叠，源点仍保留。
- 各DOS分波边界均已独立核对时，可在不同实际截止区间分别积分相加，component_intervals保留实际区间；不补零对齐。未核对则提供projection_range定位。
- 03移除计算时间、重复来源与原始JSON渲染。后台recalculations/comparisons、作者/时间和证据均保留。

## 实际来源调查

截图中300 GPa C谱初查第13版实际最高频64.48392457 THz、原图(x=663,y=896)，图框上沿y=875→67.60195435 THz，相差3.11802978 THz/21 px。旧规则把图框上沿直接当完整曲线截止，导致过强判定。

已只读查看[原图派生裁剪](assets/preflight-source-crop.png)：裁剪框为原图[640,850,800,970]，放大4倍；目标原谱为橄榄色，附近有C和累计λ文字/曲线。此图证明不能把图框上沿机械当作曲线截止，不能据此直接宣称当前点已覆盖真实谱尾。实际末端是否漏掉原线需用户在定位后对照，未自动批准。

[最后只读检查](assets/preflight-current-readonly.json)为第14版，仅有high_endpoint几何问题，自动修复预览0项。此快照不替代后续用户新保存版本；没有向用户业务API执行保存/重算或替用户确认末端，幅值依据也未代填。[用户完整截图](assets/preflight-user-request.png)原字节归档。

## 运行验证

- 前端65项通过：[日志](assets/preflight-verification/frontend-tests.txt)。覆盖末端低于图框可确认、不移点、证据失效、撤销/重做、自动连接撤销及03不渲染时间/来源。
- 后端145项通过、3项MySQL行锁测试在SQLite跳过：[日志](assets/preflight-verification/backend-tests.txt)。新增20项验证真实截止、数值预检查一次列全、精确/近似/歧义/环/重叠片段修复边界、撤销意图保留、真实HTTP持久化、证明不匹配拒绝、DOS不同截止及未连接重复样本不静默折叠。
- [当前MySQL94项](assets/preflight-current-mysql.json)通过，含纯逻辑及真实正式HTTP/事务测试；原16集合/66运行前后数量和逐行哈希不变，无测试残留、DDL或全表清理。
- [5套浏览器44场景](assets/preflight-verification/verified-suite-summary.json)通过：新增末端/自动修复6场景，回归重算8、定位7、材料恢复8和编辑吸附15。正式React/HTTP/隔离SQLite，全部API只重定向本次测试服务，不向业务API写数据。
- 新增完整闭环：问题坐标→最高频点居中→原图依据→确认→撤销/重做→保存→实际频段计算成功；再移端点→旧确认失效→重新定位。精确断端自动连接后计算成功、原点全部保留、定位/撤销/保存后再次计算不加回；DOS定位正确分波及390px布局通过。
- 已查看[末端差距与坐标](assets/preflight-verification/final/preflight/preflight-endpoint-problem.png)、[编辑器确认](assets/preflight-verification/final/preflight/preflight-endpoint-confirmed-editor.png)、[实际范围计算结果](assets/preflight-verification/final/preflight/preflight-actual-range-result.png)、[自动修复记录](assets/preflight-verification/final/preflight/preflight-auto-connected.png)。
- 正式TypeScript/Vite构建通过：[日志](assets/preflight-verification/build.txt)，既有3Dmol eval及大包提示仍存在。
- [Demo保护](assets/preflight-verification/demo-protection.json)前后文件哈希一致；正式调参也未修改。

## 证据与边界

FR-062→topology/preflight与TraceDiagnostics；FR-063→highEndpoint及manual保存校验/编辑器历史；FR-064→prepare_repairs、coincident及自动操作记录/撤销；FR-065→SpectrumMetrics精简。SC-035至037由上述单元、HTTP/MySQL和真实浏览器闭环共同证明，不以静态源码断言代替运行。

可靠自动修复不扩展为补造频率/幅值或按距离猜连接。端点确认不等于整谱科学采纳，也不自动满足幅值/单位依据。旧URL恢复V1至V4仍是独立问题。本次没有推送、部署、AI重新提取或数据库结构变更，远程Spec链接仍待验证。

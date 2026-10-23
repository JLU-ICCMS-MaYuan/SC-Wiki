# LaSc₂H₂₄ 290 GPa 重复谱入口实查

日期：2026-10-23。仅查询本机业务库，显式 START TRANSACTION READ ONLY，随后 rollback；未修改科学记录、未运行模型或重新提取。

## 结论

重复与零频不达标是两个独立问题。频率范围不是集合唯一键，强制从零开始本身不能阻止同图重复建集合。前两轮仅修改独立 Demo，正式分组与提取代码尚未接入新规则。

## 当前数据库事实

目标 upload/c16cc627a0c04dc8ad4289624d1da80a，state-5；三集合的图注均为 290 GPa，来源文件、PDF 第 4 页、source_key、原图图像哈希与 PDF 图框完全相同。

| 集合 | panel_key | 内容 | 当前入口贡献 |
| --- | --- | --- | --- |
| 702b9390fdeb43aa9af755ef935befb0 | A | DOS + α²F + 累计 λ | DOS 1、α²F 1 |
| c340f3c41b144662808c0933d1e75248 | A-alpha2f-lambda | α²F + 累计 λ | α²F 1 |
| 17d6b76963e2486aa5c4afbcbcf20d60 | A-phDOS | La/Sc/H DOS | DOS 1 |

旧合并集合 A 与后来的两个拆分集合共存。标定和排除区存在变化，不应把数值差异抹掉；但这些处理版本不能全作为同一状态的独立当前谱入口。

## 为什么第一张 α²F 卡片显示从 0 开始

两份真正的 α²F 曲线均为 0.1136621511–62.4005209515 THz、385 点。旧 A 集合的累计 λ 另有 0 THz 点，状态是 boundary_assumption，observed_amplitude 为 null、reconstructed_amplitude 为 0。它不是 α²F 的原图观测点。

spectrumGroups 把 α²F 与累计 λ 放进同一个入口组；spectrumInterval 对组内所有曲线求最小/最大频率。累计 λ 的假设边界点因此把 α²F 卡片最小值拉成 0。另一份累计 λ 没有该边界点，卡片显示 0.11366。两条 DOS 本来就都是同一个 0.11366–62.401 范围，仍重复出现。

## 零频未覆盖的直接原因

频率标定包括像素 435 对应 0 THz，线性拟合零点约为像素 434.70073。实际 ROI 终点只到像素 434，其对应频率约 0.113662 THz。extract_curve 按 ROI 内整数像素提取，没有落实从物理零频开始的硬约束。不能把当前首点直接改名为 0，也不能把 λ 的边界假设当作 α²F 零频观测。

## 对应代码

- backend/services/spectra.py::collection：按 target、target_id、source_key、panel_key 查找/新建集合。
- backend/spectra/jobs.py::discover：将自动标定返回的 panel_id 用作 panel_key；命名由 A 变为 A-alpha2f-lambda/A-phDOS 会建立新集合。
- backend/services/spectra.py::listing：排除显式 history-* 后返回各集合当前运行，没有本例旧合并集合被拆分替代的关系。
- frontend/src/lib/propertySpectra.ts::spectrumGroups：每集合分别生成入口，仅合并同一集合的分波或累计谱。
- frontend/src/lib/propertySpectra.ts::spectrumInterval：对全部组内曲线求包络。
- backend/spectra/digitize.py::extract_curve：逐 ROI 整数像素映射频率。

## 纳入正式接入的修正规则

1. 同一材料状态的 α²F 与 DOS 各保留一个当前查看入口；同一来源谱的重新标定、重提取与合并/拆分识别属于历史版本，不能因 panel_id 或频率范围变化成为额外当前谱。
2. 保留旧运行、来源、标定与核对历史，不按最小频率或“最新时间”静默判定科学正确版本；多个来源/候选在单一入口内明确其当前选择或待核对状态。
3. α²F 卡片只用 α²F 自身范围；累计 λ 单独记录范围和边界假设，不能代替 α²F 覆盖证明。
4. 两种谱从真实 0 频率边界定位与采样；缺原图范围或边界不可辨时标记提取不完整，不以补零或改标签满足约束。
5. 回归应覆盖旧合并+新拆分并存、重跑后 panel_id 改名、频段变化、累计 λ 单独带零边界，以及多分波共同范围。验收需真实页面各只有一个入口且历史可追溯。

以上是后续正式实现要求，当前未修改正式代码或数据库。机器证据为 assets/lasc-290-duplicate-diagnosis.json；截图 IMG-007/008 可复查。

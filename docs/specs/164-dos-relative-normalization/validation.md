# 验证记录

日期：2026-10-27（Asia/Shanghai）。Issue：[#164](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/164)。

本文保留各次历史验证；最新有效规则见文末“单位置于列标题”。此前关于频段确认的行为描述已被该修订取代。

## 自动验证

- 后端：194 passed、6 skipped。覆盖全部 test_spectra*.py 与 test_alpha2f_relative.py。6 项跳过为需明确授权 MySQL 的集成/并发验证，本次使用 SQLite，不能视为 MySQL 验收。
- 前端：5 个文件、45 项测试通过，覆盖新增 DOS 组件、重算、α²F 相对计算、旧谱工作区及新标签导航。
- 前端生产构建通过。现有 3Dmol eval 和大包提示仍存在；未修改核心依赖。
- git diff --check 通过。
- 测试环境 DATABASE_URL=sqlite:///:memory:，JWT 为固定测试值；正式业务数据库未参与测试。

## 科学与生命周期证据

| 验收 | 实际证据 |
|---|---|
| SC-001 | test_pixel_area_without_n_and_wrong_ratio_not_forced、缺 N 的真实 HTTP 与浏览器 |
| SC-002 | .001、1、37、1e6 共同比例缩放测试；占比、归一化谱和模式积分误差小于 1e-9 |
| SC-003 | 同一合成图的 THz/cm-1 频率和密度成对转换，实际 extract_panel 路径结果一致 |
| SC-004 | 原胞 LaH2：预期 3/6，面积比 4/5，输出模式 4/5 并保留偏差 |
| SC-005 | 缺 N、尺度、投影、定义、频段、裁峰、缺口、回折及错配元素分别阻断依赖项；其他面积保留 |
| SC-006 | 正式重算 HTTP 新版本、旧版本不变、409 冲突、人工编辑清除候选、公开隐藏/限定过滤、CSV 当前候选和浏览器 |

## 浏览器

正式 React 页面运行在 127.0.0.1:5175；全部 /api 请求转发到 127.0.0.1:8194 的隔离 FastAPI/SQLite，未向业务 API 写入。
合成谱使用 LaH2 三原子结构，La/H 像素面积 16/20、C=0.25；另一个材料状态只有化学式。
真实点击重新计算并检查持久化数据；刷新重复计算不累乘 C；切换密度刻度不改变原图路径、不发写请求。1440px 与 390px 已截图并人工查看，窄屏表格局部滚动，不撑开页面。浏览器 pageerror 为零。
首轮窄屏断言在侧栏收拢动画结束前执行失败；等待 500ms 稳定布局后通过，无产品代码掩盖该检查。

- [机器报告](validation/browser-report.json)
- [桌面](validation/dos-desktop.png)
- [窄屏](validation/dos-mobile.png)
- [缺少原胞 N](validation/dos-no-n.png)

早期测试夹具启动曾使用错误的文件存储环境变量，写入默认目录的固定测试图名；随后改为 FILE_STORAGE_LOCAL_ROOT 并在新测试入口强制校验其位于临时目录内，重新建立隔离运行。本次新增的默认目录测试图已清理，已有测试图未删除。该过程未连接或写入业务数据库。

## 范围与限制

真实用户谱未重提取、未回填、未替用户确认完整频段或标准投影；截图中的回折仍遵守现有检查。已有记录缺少完整频段证据时归一化继续提示缺失，但有效相对面积可独立计算。
本次未部署、未推送，不把源码与隔离验收当作生产生效或该论文科学准确性的证明。远程 Spec 链接待授权推送后核验，Issue 保持开放。

## 元素比例展示补充验证

2026-10-27：按用户反馈将占比进一步换算为以同一元素为1的近似比例，优先与当前化学式比较；以最大占比差（百分点）表示差距，不新增自动通过阈值。
- 后端针对 DOS 相对积分、重算和详情：75 passed、1 个 MySQL 并发测试跳过。
- 前端 DOS 与重算组件：11 项通过；生产构建通过。
- 新增测试覆盖无 N/缺完整频段确认时仍输出比例估计、共同倍率消除、化学式与结构冲突时明确参考、零面积和元素集合不匹配。
- 浏览器正式重算验证 LaH2 面积估计 1:1.25、化学式 1:2、最大占比差 11.11 个百分点；桌面和390px、刷新不累乘与无N场景通过，无 pageerror。隔离 SQLite 和文件均位于 /tmp/scwiki-manual-test-dos164-ratio/。
- 频段提示现明确缺少确认记录不等于发现缺失，合并所有受影响元素；频段不完整或未知时注明比例仅为当前已积分范围估计，仍不自动授予完整频段确认。

[补充浏览器报告](validation/element-ratio/browser-report.json) · [桌面](validation/element-ratio/dos-desktop.png) · [窄屏](validation/element-ratio/dos-mobile.png) · [无N](validation/element-ratio/dos-no-n.png)


## 删除频段确认门槛

2026-10-27，按用户明确要求删除完整频段确认字段/勾选项和高频边界记录的 DOS 归一化检查。实际计算使用已保存样本，不重新读原图；保留断线、回折、零频、无效值和已记录裁峰检查。
- 后端全部 test_spectra*.py 加 test_alpha2f_relative.py：207 passed、6 skipped；跳过项为需授权 MySQL 的测试。
- 前端 DOS、重新计算和工作区组件：14 项通过；生产构建通过。
- 新增 9 组标记/高频边界组合验证：标记缺失/false/true 与上限未知/低于末点/远高于末点均不阻止当前样本归一化，实际积分范围保持0–0.9 THz，总模式归一化为9，源点不改写。
- 旧标定字段可读但不重新保存，新字段模型不包含该标记；其他未知字段仍拒绝。
- 旧方法 dos-relative-v1 的已保存失败原因不再渲染，提示重新计算；dos-relative-v2 按新规则计算。CSV 两版候选兼容。
- 本轮未重复运行浏览器；已有浏览器截图属于此前版本，不能作为移除门槛后的界面截图。当前变更通过实际 HTTP 路由回归、组件测试及构建核验。
- 未回填、未重新提取业务谱，未推送或部署。


## TDOS 独立归一化（2026-11-04）

### 结论与验收范围

本轮修订 #164 原设计对 TDOS 共用元素门槛的缺陷。明确总谱及标准定义后，不再要求元素完整性和分波共同尺度；未知单线、单元素分波和总谱/分波混合不能借此放行。保留 N、结构一致性、数值/连线和裁峰条件。元素比较留空，总谱实际范围保留，独立绝对检查不使用归一化结果。报告与候选使用 dos-relative-v4，重算版本为 spectra-recalculate-tdos-v2；旧报告要求重算，历史源数据未批量改写。

### 修复前与自动验证

- 新增用例在修复前为 13 failed；原始输出见 [before-fix.txt](validation/tdos/before-fix.txt)。另用起始提交的原始计算器独立复现“元素完整性 → 共同尺度”两次阻断，见 [baseline-probe.json](validation/tdos/baseline-probe.json)。
- 最终后端谱/α²F 回归 289 passed、6 skipped；其中 DOS 专项 70 passed。跳过项需授权 MySQL，未宣称 MySQL 验收。
- 前端相关 5 文件 55 项通过；表单契约 11 文件 150 项通过；8 项变异行为全部检出；科学字段契约 v1 基线通过，未改标准字段或摘要。
- TypeScript 与前端生产构建通过；既有 3Dmol eval 和大包提示仍存在。
- 正式 React + HTTP + 隔离 SQLite 浏览器检查 8 项通过，0 页面异常；包括元素分波原回归、TDOS、真实保存描线、刷新重复重算、CSV、1440px/390px。仅对专用 127.0.0.1:8194 服务写入，没有业务API写入。见 [browser-report.json](validation/tdos/browser-report.json)。

### 原始来源重新识别与数值提取

来源为《2012 CaH6--suppliment-王晖.pdf》第17页 Figure S15，PDF SHA-256 为 630283a3cbfb7d8fb8624c957de2b9958f9ece57a28b3a78830647b32535d348。从原PDF重新取得原生内嵌图，字节哈希 03700ded01a105cb374c95a4c613dc18174c84545c2d702a1ab52d5da84e92b4 与业务来源一致。

本轮真实调用 gpt-6.1-sol，从原图与该页文字重新识别上下两个相邻压力面板，再执行正式 calibrate → extract_panel。两者均明确 projection=total、physical_definition_confirmed=true；新数值描线仍有缺失点，未形成有效积分，程序继续阻断，未伪称新提取通过。响应及结果分别保存在 [fresh-model-response.json](validation/tdos/fresh-model-response.json)、[source-report.json](validation/tdos/source-report.json)，并有固定重放测试。原始图为 [source.png](validation/tdos/source.png)。这不是整篇解析通过，也不是自动描线缺失问题已修复。

### 已保存人工描线的独立重算

截图对应旧记录 projection=null、physical_definition_confirmed=false，不能只凭名称中有 total 就确认身份。只读取得原记录后，在隔离副本中仅依据本轮新读图确认身份，沿用原人工描线、像素坐标及连线。实际重算：N=7，总面积约2596像素·THz，C=0.008089269069713752，归一化总模式21，范围3.6556–58.648 THz；逐元素占比/模式比较未生成。源图只有任意单位，原始绝对密度积分仍不可用。

该副本经过正式HTTP重算保存新运行、数据库重读与CSV导出，原始曲线不变、重复重算系数不累乘；历史与限定频段回归保留。可复现输入见 [source-fixture.json](validation/tdos/source-fixture.json)。已实际查看 [桌面截图](validation/tdos/dos-real-source-desktop.png) 和 [窄屏截图](validation/tdos/dos-real-source-mobile.png)，结果可读，窄屏表格局部滚动、无整页横向溢出。

### 来源、复用和边界

- 原PDF、原图及页文字已核对；不重做无关文字提取，未重提整篇字段。
- 新模型重跑的是受影响的总谱身份/标定；实际新数值提取失败保持失败。人工描线明确复用，未冒充模型重新提取。
- 原胞 N 来自当前已保存结构，经 ASE/spglib 验证为7；不从 CaH6 化学式推断原胞倍数。
- 用户业务库与返修草稿未写入；截图旧业务记录仍保留未确认身份，不会因升级源码自动转为总谱。本轮不包含业务数据修复、推送、部署或历史回填。
- Issue 保持 OPEN，远程 Spec 双向链接仍待另行授权推送后核验。汇总见 [checks.json](validation/tdos/checks.json)。


## 纵轴刻度优先的文档修订与数值复核（2026-11-04）

用户认可刻度优先方案，并要求继续修改既有Issue和Spec。本轮只更新需求/设计/待办，计算代码、页面、业务记录和Overview均未改动；前述TDOS回归通过记录不作为本轮新规则已实现的证据。

只读复用[固定人工描线夹具](validation/tdos/source-fixture.json)，SHA-256为1b14baa15dc6b9f13bcbb84a88205e16952e12ec3c59a4f8139669ef90d2c19c。按当前已保存纵轴标定及同一连线，用connected_samples和梯形积分复核：来源积分6.308648445665745任意单位·THz；像素面积2596.0318316798316像素·THz。N=7时对应系数分别为3.32876370919475和0.008089269069713752；归一化谱点最大绝对差8.881784197001252e-16。

用户选中的“6.30865 任意单位·THz”是上述来源积分按显示精度呈现，不是原论文直接报告值，不是原始绝对模式数，也不是模型新描线成功的证据。本轮未调用模型或写业务库。T016–T019的代码、页面及端到端验收仍待执行。


## 纵轴刻度优先的代码实现与验收（2026-11-04）

用户在文档确认后明确要求“开始落地代码”。实现新报告/候选dos-relative-v5和重算版本spectra-recalculate-axis-v3：当前人工纵轴标定优先，其次来源刻度，无可用数值刻度时才用像素。每条曲线先独立积分，任意单位、缺N或身份未知不再阻止有效来源数值积分。单位不一致时保留独立结果，禁止直接相加。α²F、原始点、独立绝对积分、历史/公开权限及科学采纳边界保留。

### 回归和正式路径

- 修改前新增5项失败，见[失败输出](validation/axis-calibration/before-fix.txt)；修复后DOS专项77项通过。后端谱/α²F总回归296 passed、6项需授权MySQL跳过；未宣称MySQL验收。
- 前端相关5文件57项通过；表单契约11文件150项通过，四类宿主8项变异全部检出；科学字段契约v1及TypeScript/生产构建通过。既有大包/3Dmol eval提示保留。
- 正式HTTP/SQLite测试覆盖像素与当前标定两种路径的新运行保存、重读、旧运行及原点不变、CSV来源积分/单位/依据与候选密度；不是只测试计算子函数。
- 正式React+HTTP+隔离SQLite浏览器10项检查、0页面异常；包括纵轴来源积分6.30865、CSV一致、原刻度/归一化切换无写请求且描线几何不变、刷新重算不累乘、1440px/390px无整页溢出；身份未知且无N仍显示独立来源积分。见[browser-report.json](validation/axis-calibration/browser-report.json)。

### 真实来源与复用边界

从原PDF重新取得第17页内嵌图，PDF/图像哈希与既有source-fixture来源一致。真实调用gpt-6.1-sol，按当前发现提示重新标定上下两个相邻压力面板；均将纵轴识别为arbitrary_units并执行正式extract_panel。新自动描线仍有缺失点（上图202、下图194），未声称新自动提取可积分。原模型响应和失败结果分别保留在[fresh-model-response.json](validation/axis-calibration/fresh-model-response.json)、[source-report.json](validation/axis-calibration/source-report.json)。

成功数值验证明确复用validation/tdos/source-fixture.json中原有人工描线、连线与当前标定，不重画曲线。独立积分为6.308648445665745任意单位·THz，按显示精度为6.30865；确认标准TDOS、N=7后系数3.32876370919475、总模式21；与像素路径归一化谱点差在1e-9以内。原图为任意单位，未把该来源积分称为原始模式数。

已实际查看[桌面](validation/axis-calibration/desktop.png)及[窄屏](validation/axis-calibration/mobile.png)截图；另保留[未知身份且无N](validation/axis-calibration/unknown-identity.png)页面。02显示原纵轴幅值与按3N刻度，03显示每条曲线实际积分单位和幅值依据。CSV增加dos_integral、dos_integral_unit、dos_amplitude_basis，保留原始点值。

本轮不写用户业务草稿或来源身份，不迁移、不回填、不推送、不部署。旧v1–v4报告需点“重新计算”生成v5；独立来源积分无需TDOS确认，但3N归一化仍需要。Issue保持OPEN，远程文档链接待另行推送后实际核验。


## 五列结果与独立元素清单（2026-11-04）

本轮按用户要求将积分结果固定为五列：元素／TDOS、积分范围、积分值、面积占比、原子数占比。内部曲线ID不再作为名称或范围显示；数值后紧接单位与幅值依据，并保持同行。明确总谱显示TDOS，明确元素显示元素名，未确认投影显示待确认，不根据ID或单线数量改写科学身份。

材料原子数占比现在由独立composition提供：优先已知化学式，缺少时沿用可信结构计数，不依赖元素分波完整性、N或归一化成功。表格据此补齐无分波元素行，范围、积分、面积占比为—，不会将占位行保存为曲线或送入积分。旧v5无composition时只读取已有normalization.structure_evidence.species_counts；原始点、旧结果与业务草稿均不改写。

### 自动与正式页面验证

- 修改前新增后端2项、组件2项失败，见[后端失败](validation/five-column-table/before-backend.txt)、[组件失败](validation/five-column-table/before-ui.txt)。修复后DOS专项79项通过，谱/α²F后端298 passed、6项需授权MySQL跳过；不是MySQL验收。
- 前端相关5文件59项通过，表单契约11文件150项通过；四类宿主8项变异全部检出；科学字段契约v1与TypeScript/生产构建通过。没有修改标准科学表单键或摘要。
- 后端验证在缺少元素分波、身份未确认和无N时仍返回已知化学计量，化学式优先于结构；公开过滤只保留可见曲线，组成不包含隐藏曲线ID或派生值，不扩大可见范围。
- 正式React+HTTP+隔离SQLite浏览器11项检查通过、0页面异常。CaH6仅总谱时显示TDOS、Ca、H三行；Ca/H原子数占比14.29%/85.71%，未提供分波的范围/积分/面积比为—。实测总谱积分仍为6.30865任意单位·THz；无额外曲线或数值生成。
- 浏览器实际检查五列表头、未知投影名称、ID隐藏，以及文本边界框确认积分数值和单位同行；1440px与390px均无整页横向溢出，表格局部滚动。原始描线与重复重算、CSV回归保持。报告见[browser-report.json](validation/five-column-table/browser-report.json)。

已实际查看[桌面截图](validation/five-column-table/desktop.png)和[窄屏截图](validation/five-column-table/mobile.png)，另保留[未知投影页面](validation/five-column-table/unknown-projection.png)。截图原材料IMG-005按原始字节归档、哈希及尺寸核验完成。

本轮只暴露已有化学式/结构计数和调整展示，没有修改PDF/模型提取、标定或积分算法，因此未重提PDF或调用模型；复用已核验原图及人工描线夹具，不宣称新自动描线通过。没有业务写入、迁移、批量回填、推送或部署；Issue保持OPEN，远程Spec链接待另行推送后实际核验。


## 单位置于列标题（2026-11-04）

用户明确纠正为积分值（实际单位 · 幅值依据）、积分范围（实际频率单位）的表头格式，取代上一轮将单位跟随每个数值的显示。当前示例为积分值（任意单位·THz · 纵轴刻度）、积分范围（THz），数据格仅显示6.30865和3.6556–58.648。像素单位同样移入列标题；混合积分单位/幅值依据分别成表，避免同一个标题错误套用所有数值；材料元素空行保留且不重复。

本轮只修改前端展示，现有范围字段frequency_interval_thz仍为规范THz，不将原图cm-1或meV重标到未换算的数值。后端、原始描线、积分、CSV及科学身份不变，无模型调用或业务数据写入。

验证：前端相关5文件60项通过（含混合单位独立数值/表头回归）；表单契约11文件150项通过，四类宿主8项变异均检出，TypeScript与生产构建通过。正式React+HTTP+隔离SQLite浏览器11项检查、0页面异常，实际检查列标题与数值格文本、元素空行、原刻度切换/重复重算/CSV及1440px/390px。不是后端数值算法变更，本轮未重跑后端或PDF提取，不沿用历史回归宣称重新执行。

已查看[桌面截图](validation/unit-headings/desktop.png)及[窄屏截图](validation/unit-headings/mobile.png)，单位在表头括号，数据格没有重复单位；局部横向滚动保留、无整页溢出。报告见[browser-report.json](validation/unit-headings/browser-report.json)。未推送、未部署；Issue保持OPEN，远程Spec链接仍待另行核验。

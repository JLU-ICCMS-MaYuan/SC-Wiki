# 验证记录

日期：2026-10-27（Asia/Shanghai）。Issue：[#164](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/164)。

本文保留各次历史验证；最新有效规则见文末“TDOS 独立归一化”。此前关于频段确认的行为描述已被该修订取代。

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

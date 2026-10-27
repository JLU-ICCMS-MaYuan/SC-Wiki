# 验证记录

日期：2026-10-27（Asia/Shanghai）。Issue：[#164](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/164)。

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

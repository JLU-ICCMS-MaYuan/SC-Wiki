# 实现与验收

日期：2026-10-28。分支：mayuan。Issue：[#167](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/167)。

## 已实现行为

正式详情、编辑器及独立Demo的人工零频确认卡、专用标线/补点工具、辅助读数、确认状态和后端报告已删除。新文档不生成zero；旧字段只在边界忽略，不改历史运行。普通坐标轴刻度、两点标定和幅值零基线保留。

首点可为正频率，按实际区间积分。无0刻度也可用现有刻度提取，不扩展ROI或补造低频样本。α²F结果记录真实上下限和覆盖状态；DOS分别记录各分波实际范围。方法版本为alpha2f-relative-v2、dos-relative-v3和spectra-recalculate-sampled-range-v1，旧核对错误不再展示为操作要求。

微小回折修正不再依赖人工零点ID，数值端点/真实0和低频保护保持。真实0处α²F非零仍报告积分发散；缺口、负数、非有限值、分叉/环、未解决回折及权限/版本检查保留。机器级两项相消误差仅在坐标换算中消除，不把可分辨的正频率改0。

## 自动验证

| 层级 | 结果与证据 |
| --- | --- |
| 后端谱模块 | 226通过、6跳过；[日志](assets/backend-tests.log)。跳过项需要另行授权的MySQL环境，本次仅隔离SQLite |
| 谱数学回归 | 40通过；[日志](assets/math-tests.log) |
| 正式前端 | 15文件、107通过；[日志](assets/frontend-tests.log)；[构建](assets/frontend-build.log)通过 |
| Demo | 4文件、36通过；[日志](assets/demo-tests.log)；[构建](assets/demo-build.log)通过 |
| 正式页面浏览器 | 6组场景通过；[报告](assets/browser-validation.json)，无页面脚本错误 |
| Demo浏览器 | 49项通过；[报告](assets/demo-browser-validation.json)，无业务API请求或脚本错误 |
| 实际导出 | α²F 117行、DOS 6行；[报告](assets/export-validation.json)。JSON保留真实范围，CSV首频为0.2 THz且新版DOS归一化列有值 |

后端命令：`DATABASE_URL="sqlite:///:memory:" JWT_SECRET_KEY="isolated-unit-test" /Users/mayuan/software/miniconda3/envs/sc-wiki/bin/python -m pytest backend/tests/test_spectra*.py -q --disable-warnings`。数学路径为`scripts/phonon_spectra_demo/tests`。正式Vitest执行谱相关13个文件及两个谱导航文件，完整命令见日志。Demo使用其package.json的test与build。

正式浏览器运行`tests/01_decentralized_uploading/spectrum-no-zero-production.cjs`，真实5173前端的所有/api请求转发隔离8199 FastAPI与SQLite；夹具为`backend/tests/no_zero_review_server.py`，文件存储也位于临时测试目录。身份依赖使用隔离用户，不冒充真实JWT/业务数据库端到端验收。Demo使用独立5190服务和新浏览器上下文，输出另存临时目录后归档，不覆盖历史证据或用户草稿。

## 场景与需求覆盖

| 需求 | 事实证据 |
| --- | --- |
| FR-001/002/007、SC-001/003/004 | 正式及Demo无核对入口；HTTP无zero保存、旧zero忽略；旧诊断过滤；模块/导入搜索无专用实现 |
| FR-003/005、SC-002 | 解析例验证0.2–6.2 THz的λ相关积分与ωlog；正式页0.2–6 THz计算且不改点，LaH2的0.2–1.2 THz归一化总数9；JSON/CSV保留范围 |
| FR-004、SC-003 | 无0刻度正常提取、ROI不扩展、分数像素0不补样本；Demo普通标定/刻度通过 |
| FR-006/008、SC-004/005 | 回折模块回归、实际0处非零α²F发散、机器舍入与小正频区分、拓扑/负数/版本/权限回归 |
| FR-009、SC-006 | 论文λ参考归一化、原胞N和投影检查；切换La/H连续保存保留两次修改，回读/重算有效；旧URL直接追新，无额外写请求 |

截图已检查：[α²F桌面](assets/alpha-positive-range.png)、[α²F窄屏](assets/alpha-mobile.png)、[DOS桌面](assets/dos-positive-3n.png)、[DOS窄屏](assets/dos-mobile.png)、[Demo编辑器](assets/chain-demo-demo-dos-editor.png)、[Demo窄屏](assets/chain-demo-demo-mobile-editor.png)。390px下页面无横向溢出，表格在各自容器内滚动。

## 保留项与交付边界

两处dragInfluence.ts与任务前SHA256一致：正式d6e16d45e825d79a0e07f236d3662aa96b42007faea685d5049ec97e4a7cd23e、Demo b3c8c9e32bfe0698f80def9171844e26b819e0c50e5e3feaebb62a049311f4e0；不纳入本次提交。Demo夹具逐对象核对仅移除zero字段，其余曲线数据不变。

前两个修改已经回写#161及其Spec：自动恢复最新结果6c0c9d53、保存并继续编辑21d89f6e。当前Overview已更新为实际区间计算，旧Spec保留需求历史并注明由#167取代。根README安装/启动规则未变。

本地实时开发继续使用5173 Vite与8000 Uvicorn的源码热重载；健康检查返回ok。无业务数据回填、无阿里云或Docker发布。未推送，Issue的远程Spec链接仍待推送后核验，因此保持开放。通过的是软件行为和数值回归，不等于原图提取精度或缺测频段的科学完整性已获验证。

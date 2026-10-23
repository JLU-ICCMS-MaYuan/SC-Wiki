# #154/#155 正式实现验证（2026-10-23）

## 已交付代码

- 正式 PropertySpectra 入口：新标签原生链接，不保存主表单；材料状态每类型一个入口，旧合并/拆分记录仍保留。
- 正式 SpectrumDetailPage / SpectrumDetailView：四区、单图三模式、来源轴向及正向、DOS 全部/单分波、定高滚动点表、中文真实来源状态与幅值绝对差。历史读取、历史导出、版本冲突、图像失败重试与无数据状态可用。
- 后端 v3：稳定面板身份、真实零频刻度约束/像素采样、α²F 独立幅值依据门、原始绝对 DOS 积分与 3N 的绝对/非负百分比偏差；不提供满足判断。
- 不改写旧谱数值、采纳结果或用户表单。没有数据库迁移，没有部署/重启命令，没有推送。

## 验证

1. 后端与共享谱数学：86 项通过。命令为项目 Python 运行 pytest backend/tests/test_spectra.py backend/tests/test_spectra_details.py scripts/phonon_spectra_demo/tests -q。
2. 前端：29 项通过，覆盖导航、原输入保留、不调用保存、唯一入口、累计零点不扩大 α²F 范围、历史与指标、归属双版本及只读边界。
3. 隔离 SQLite HTTP：正式 FastAPI 路由/真实 context 权限判断，历史列表、旧运行/CSV 导出、404 与匿名 403 通过；只替换测试用户认证和上传记录来源，不跳过谱目标授权。
4. 生产前端构建通过。现有 3Dmol eval 与大 bundle 提示未由本改动引入。
5. 正式 App 路由浏览器：以本机数据库只读快照供应网络，验证实际 290 GPa 谱、单图三模式、分波、历史、固定点表和 390px。pageerror=0、业务写请求=0。不是实际网关端到端验收。
6. 本机数据库只读查询当前谱列表成功；三个 290 GPa 集合来源图像哈希已核对。读取真实原图后调用 v3 extract_panel，全部从真实零频位置采样，零频幅值均不可辨，因此保留 null/missing 且 needs_review；α²F 因缺独立幅值依据不积分，没有假造零幅值。

## 证据

共用 ../154-alpha2f-detail-demo/assets/production-browser.json、production-zero-extraction.json、production-alpha/dos-desktop.png、production-alpha/dos-mobile.png 和 mobile-plot.png。
测试文件 backend/tests/test_spectra_details.py 与 tests/01_decentralized_uploading/spectra-detail-browser.cjs。浏览器脚本读取外部只读快照，不将业务草稿/凭据提交到 Git。

## 边界与尚未通过的验收

- 历史 500：本机 frontend.log 有谱请求到 8080 的 ECONNREFUSED，不能唯一归因用户截图；当前列表成功，新入口消除查看前保存依赖、保留真实错误重试。未以负复现声称所有服务故障均修复。
- 旧 v2 谱不自动回填，不会仅因 UI 更新变成零频完整数据；须后续在明确目标环境通过正式重提取路径处理。
- 290 GPa 的真实零频幅值及 α²F 独立刻度仍待科学核对。本轮没有调用模型、没有修改业务谱或自动 human_confirmed。
- 尚未推送，远程 Spec 双向链接未验证；两个 Issue 保持 OPEN，不将软件实现冒充科学数据和部署验收。

## 当前业务库的正式 HTTP 路由只读复验

使用正式 FastAPI 路由和本机业务库只读事务（测试注入任务所有者，未经过真实认证/网关）：列表、290 GPa DOS 原图、CSV、历史均返回 200。数据库未写入。证据见 ../155-phonon-dos-detail-demo/production-http-readonly.json。该结果证明当前数据可经路由序列化和存储读取，不能反推过去截图 500 的唯一原因。

相同输入重复提取时，已有数值的 needs_review 结果复用，不覆盖原观测；新增缓存不可变性回归通过。

## 子图裁切与比例修订

本轮更新为 88 项后端/数学、33 项前端通过，真实谱快照验证裁切和同像素叠加、左右分区及滑动选项。详见 [裁切验证](../154-alpha2f-detail-demo/crop-validation.md)，后续自动化方案见 [裁切调研](../154-alpha2f-detail-demo/crop-research.md)。

## 低频伪峰修复

现已通过 94 项后端/数学、34 项前端、构建及实际新运行回绘验证。详见 false-peak-diagnosis.md；本次按用户要求仅对本机 290 GPa α²F 集合复用旧标定生成 v4 新运行，旧版本和其他材料保留，未新调模型。之前本轮“业务谱未重提取”的描述属于此前阶段，不适用于此次明确的定向缺陷修复。

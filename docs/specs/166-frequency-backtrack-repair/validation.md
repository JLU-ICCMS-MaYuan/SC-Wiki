# 验证记录

日期：2026-10-27，Asia/Shanghai。Issue：[#166](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/166)。

## 实现与科学边界

后端仅在主动重算时处理有匹配编辑文档的连续唯一描线。PAVA识别冲突块，再按原图每点0.5px、固定点、图框、原始邻点和块分界联合限制候选。非冲突区域不变，频率严格递增，幅值、ID、连线保持。无解时拒绝该块，不能把报错消失当科学验证。

零频和端点按原坐标精确保留；α²F距零频≤1原图像素的样本固定。最小正向间隔用于数值可计算性，不表示图像具有该分辨率。批次记录分片满足既有4000字符/操作及文档4MB、5000操作限制。

## 自动验证

- 后端：239 passed、6 skipped；全部test_spectra*.py与test_alpha2f_relative.py。6项跳过为需单独授权MySQL的验证，本轮无该授权。
- 前端：14个文件、102项测试通过，覆盖频率撤销/报告和现有谱编辑/导航回归。
- 生产构建通过，现有大包和3Dmol eval提示不属于本次新增。
- git diff --check通过。

命令（仓库根）：

    DATABASE_URL="sqlite:///:memory:" JWT_SECRET_KEY="isolated-repair-test-secret" /Users/mayuan/software/miniconda3/envs/sc-wiki/bin/python -m pytest backend/tests/test_spectra*.py backend/tests/test_alpha2f_relative.py -q
    npm --prefix frontend run test:upload-ui -- tests/01_decentralized_uploading/spectrum-*.test.tsx tests/01_decentralized_uploading/property-spectra-navigation.test.tsx tests/01_decentralized_uploading/upload-spectrum-save-navigation.test.tsx
    npm --prefix frontend run build

## FR/SC证据

| 验收 | 具体证据 |
|---|---|
| SC-001 | 孤立/连续/重复频率、边界均值夹取、横纵轴、反向路径、完全重合连接表示；幅值/ID/连接不变 |
| SC-002 | 大回退、连续小回退累计超限、α²F低频固定、原图越界、不一致数据、分叉/环/断口、历史容量不足原样保留 |
| SC-003 | 正式HTTP人工保存→重算→编辑读取→CSV；新运行、旧运行不变、409冲突、重复重算幂等 |
| SC-004 | 最近分片批次撤销、后续频率/标定/点删除拒绝覆盖、幅值变化保留、撤销/重做、实际浏览器定位保存及再重算 |
| SC-005 | 80组合成随机冲突检查原合法边不失效；截图四对可读y坐标作为独立几何用例；规模结果见下文 |
| SC-006 | 既有谱/α²F后端回归及谱前端回归；公开输出不包含内部频率修正报告 |

截图四对独立用例均可在上限内修正，但未读取真实业务整条曲线，不能宣称截图全部12处均已修复。

## 性能

1000、5000、20000点分别进行一次含两点微小回折的完整后端处理，实测约0.0034、0.0156、0.1142秒，详见[原始测量](validation/performance.json)。PAVA和路径处理为线性，记录分片长度有固定上限。该测量不是所有数据的最坏耗时，也不是端到端或浏览器帧率保证；拖动帧未加入此算法。

## 浏览器验收

前端5175，后端8196，所有API重定向隔离FastAPI/SQLite；文件与数据库位于/tmp/scwiki-manual-test-repair166-final/。身份由测试夹具提供，未向真实业务API/数据库写入。6组场景通过，无pageerror：

1. 纵轴α²F人工回折重算修正两点、幅值不变、积分可用、青色高亮和报告。
2. 刷新与重复重算不累积位移，报告保留且本次新增为0。
3. 点击定位打开编辑器，撤销后保存并重算，保持撤销意图和真实回折诊断。
4. 再次人工频率编辑后可重新自动处理；修正后继续改频率，直接撤销按钮禁用。
5. 横轴DOS同样处理，其他分波不变，390px报告不撑开页面。
6. 大于限额的回折保持原点和诊断，不显示虚假修复成功。

[机器报告](validation/frequency-repair-browser.json) · [重算结果](validation/recalculated.png) · [编辑器撤销](validation/editor-undo.png) · [尊重撤销](validation/undo-respected.png) · [窄屏DOS](validation/dos-mobile.png) · [大回折保留](validation/large-kept.png)。

## 数据保护与交付范围

原图IMG-001已Pillow完整解码并检查哈希/尺寸。用户已有联动参数及独立Demo共27个源文件与此前基线哈希一致，不纳入提交。未改变手动拖动方式、未自动采纳、未重读/重提取或回填用户业务谱。
未推送、未部署，远程Spec链接保持待验证，Issue不关闭。源码和隔离测试通过不代表生产发布或论文科学正确性。

## 本地实时开发环境核验

用户后续明确选择“本地实时开发环境”。本节是对实际本机实例的只读核验，区别于前述隔离测试。

- 前端入口 http://127.0.0.1:5173 ，Vite进程工作目录为当前仓库frontend；实际HTTP模块已提供自动频率微调/撤销和两种拖动按钮。
- Python入口127.0.0.1:8000，Uvicorn以--reload --reload-dir backend运行，当前服务子进程PID 25237，启动于2026-10-27 20:26:11.751771 +08:00，晚于最终frequency_repair.py修改时间20:26:11.497793；日志确认相应文件触发重载并完成启动。
- Python /health、/readyz、Go /health和Vite首页均为HTTP 200；readyz的MySQL、Redis、对象存储、Qdrant、Neo4j检查均通过。
- 实际连接SELECT DATABASE()/@@port为scwiki/3307；Python进程中的数据库、Redis、数据目录及存储目标与当前.env配置匹配。对象存储为本机Garage 127.0.0.1:39110、scwiki-business桶；未输出口令或访问密钥。
- 当前代码来源为ecd682c8，包含用户已有未提交的联动参数设置；本轮不改变这些参数。文件存储和数据库均属于已确认的本机目标。
- 热重载已满足本次生效要求，无需额外启停/重启；未执行迁移、回填、批量重算或业务谱写入。使用者刷新谱详情并点击“重新计算”后才会触发该谱的修正。
- 此核验确认运行目标、依赖和当前前端模块；没有使用真实用户身份执行业务谱重算，不冒称已修复截图对应的12处回折。
- 详细脱敏记录见[本机运行核验](validation/local-native-runtime.json)。Git未推送，远程Spec链接仍待验证。

检查脚本首次按requests默认编码读取JavaScript时中文特征误判为不存在，改为明确UTF-8解码后全部通过；这是核验脚本解码问题，未据此修改应用代码。

## 修正后直接展示结果

用户反馈后，详情页删除已处理修正的常驻摘要、坐标列表、分页和只读青色标记；当前及已有报告都按新规则展示。结果早已随重算保存，本轮不增加“应用确认”或修改任何后端数值。未处理原因和诊断定位、编辑器内高亮/撤销仍保留。

- 16项相关前端测试通过；生产构建通过，后端未改动。
- 复用实际本地Vite 5173前端，浏览器全部API重定向至8196的隔离FastAPI/SQLite，文件与库位于/tmp/scwiki-manual-test-repair166-clean/，未触发真实业务谱写入。
- 6组浏览器场景通过：修正后直接显示新结果；刷新/重复重算不展示旧过程；编辑器撤销/保存仍有效；后续频率编辑保护；横轴DOS/390px；超限问题继续显示。pageerror为0。
- 原始反馈图IMG-002原字节归档、哈希/尺寸/完整解码通过。
- 本机5173已提供新前端，无需重启；不推送、不发布到其他环境。

[浏览器记录](validation/results-only/frequency-repair-browser.json) · [精简后的详情](validation/results-only/recalculated.png) · [窄屏DOS](validation/results-only/dos-mobile.png)。
此前截图中的修正清单属于旧版本，不再描述当前详情行为。

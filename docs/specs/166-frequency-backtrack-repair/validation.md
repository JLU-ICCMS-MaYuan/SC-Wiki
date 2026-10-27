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

# 彻底取消高频末端核对验收

日期：2026-10-27。用户明确确认：“彻底取消高频末端核对，不是放宽容差”，答复“对！”。对应FR-066至068/SC-038至039；本规则取代此前末端确认方案。

## 改动

- 后端删除high_info/endpoint_valid函数、高频端确认条件和DOS各分波上限一致性条件。α²F直接用当前保存单值路径最高频点作积分上限；DOS分别在各自保存区间积分相加，component_intervals保留区间，不延伸或补点。
- 统一诊断不再生成high_endpoint或projection_range；保留缺口、孤立点、闭环、分叉、频率重复/回折、无效/负数值、零频及幅值/单位等检查。
- 编辑器删除高频末端依据/确认控件、状态、验证函数与样式；自动连接撤销保留为独立入口。
- 旧run的highEndpoint不批量迁移或删除；GET编辑输入去掉该废弃字段，POST编辑保存忽略旧客户端字段，不以错误/过期/缺失证明拦截保存或计算。
- 详情过滤历史保存的末端核对诊断，旧门槛报错改为提示重新计算。当前源码中残留的末端错误字符串仅用于这一有界展示兼容，不参与计算判定。
- 03继续不显示时间或来源JSON，后台参考和时间记录保留。

## 验证

- 前端65项通过：[日志](assets/no-endpoint-verification/frontend-tests.txt)。包括旧诊断隐藏、旧错误不再作为门槛、自动连接撤销及各项既有UI回归。
- 后端146项通过，3项MySQL行锁测试在SQLite跳过：[日志](assets/no-endpoint-verification/backend-tests.txt)。重点覆盖图框与末点相差0.000002像素、较大空白范围、旧证明内容错误/缺失、移动末点后直接保存计算、不同DOS范围及无造点。
- [当前MySQL95项](assets/no-endpoint-current-mysql.json)通过，包含纯逻辑及真实HTTP/事务/并发测试；原16集合69运行数量和逐行哈希前后一致，无测试遗留、建表或全表清理。
- [5套浏览器44场景](assets/no-endpoint-verification/verified-suite-summary.json)通过：取消核对专用6场景，重算8、诊断7、编辑15、材料恢复8。使用正式React/HTTP/隔离SQLite，全部API只到测试服务，没有对用户实际谱执行保存、重算或确认。
- 专用场景：末点距图框0.000002px直接得到积分，原点不变；编辑器没有末端输入和确认按钮；修改最高频点后保存重算无需确认；最高频5THz、图框6THz直接积分；旧错误确认字段被忽略；DOS不同上限分别积分，不出现分波末端核对；其他缺口和撤销意图仍受保护。
- 已查看[微小差距直接计算结果](assets/no-endpoint-verification/preflight/preflight-no-endpoint-near-frame.png)。[明显不到图框也可计算](assets/no-endpoint-verification/preflight/preflight-far-below-frame.png)和[DOS不同范围](assets/no-endpoint-verification/preflight/preflight-dos-different-ranges.png)由浏览器截图归档。
- 正式TypeScript/Vite构建通过：[日志](assets/no-endpoint-verification/build.txt)，既有3Dmol eval及大包提示不属于本轮新增。
- [Demo保护](assets/no-endpoint-verification/demo-protection.json)文件内容哈希一致；用户联动参数未修改。[用户原图](assets/no-endpoint-user-request.png)按原字节保存。

## 范围说明

这是移除检查本身，不增加另一种末端确认，也不通过容差放宽实现。其他材料/权限/版本保护、零频、拓扑和幅值依据规则不变，不承诺在其他条件不足时仍生成数值。仅计算已保存数据区间，不宣称该区间自动代表完整物理谱或科学采纳。

Issue、Spec、契约、Tasks、quickstart和Overview已同步最新规则；旧Spec原话与历史验收保留以便追溯。没有部署、推送、AI重提取或数据库结构变更，远程Spec链接仍待推送后验证。

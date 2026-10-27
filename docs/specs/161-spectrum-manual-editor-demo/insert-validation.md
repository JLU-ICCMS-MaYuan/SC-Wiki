# 原线段插点与未连接片段补接验收

日期：2026-10-27。对应FR-069至072/SC-040至042。用户后续强调“不要颠覆之前逻辑”，两种加点能力同时保留，仅正式页面接入。

## 行为与实现

- 原A—B直边存在：选A、新增一点或多点、点击B，替换为A—新点链—B并退出加点，不保留旧直边造成额外闭环。
- 原A/B未连接：仍走原appendPoint/joinExistingPoint，补接描线但不删除任何原边，沿用吸附/双击结束。自由连续描线保留。
- insertDrawnPoints冻结原描线，按稳定ID验证本次新链，原隐式/connectTo/joinTo直边只作局部替换；重排新点以满足父点先于子点，反向插入也支持。原始点ID/坐标、其他边、断口及分波保留。原join边的其他父边不被覆盖。
- SourceCanvas会话记录起始快照、起点与新增ID；只有目标是原起点直接邻点时才调用替换函数，不将它变为全部加点的准入限制。其他目标沿用原逻辑。计算成本O(n+k)，不做所有点两两比较。
- 终点单击完成直边插入；撤销最终替换回到未完成的新增链，再继续撤销可逐点退回；重做保持新点ID。真正入库仍通过保存调整，既有版本冲突保护不变。
- 原点坐标不动，不自动调整频率。插点位于原点之间且频率顺序正确时能按真实路径积分；用户画出的实际回折/重复频率仍由原有检查指出。

## 验证

- 前端73项通过：[日志](assets/insert-verification/frontend-tests.txt)。新增8项专门验证从SVG命令恢复的真实边集合、正/反向、显式父边/吸附边、其他父边保持、未连目标仍可补接、撤销/联动、错误ID不变更及纵向标定。
- 后端148项通过、3项MySQL行锁在SQLite跳过：[日志](assets/insert-verification/backend-tests.txt)。新增真实HTTP两场景：直边插点及断口补接，保存回读后图为单路径、无环/分叉，原点像素不变、频率沿图递增且可计算λ。
- [当前MySQL97项](assets/insert-current-mysql.json)通过，包括纯逻辑和真实HTTP/事务；原16集合103运行数量/逐行哈希不变，临时记录精确清理，无DDL。
- [4套浏览器32场景](assets/insert-verification/verified-suite-summary.json)通过：横轴频率插点5、纵轴频率插点5、既有编辑15、坐标诊断7。实际鼠标操作放大后新增→原终点单击→撤销/重做→保存→重算，正反向均可，原点不动，无额外环/分叉；未连片段补接后同样可积分；自由描线、双击结束不被取消；DOS只修改Sc，不影响La/H，390px可保存。
- 纵向样例将原图和全部相关标定同步逆时针旋转，使用真实图片/像素变换，不仅靠静态代码断言。测试辅助服务每谱使用自己的来源图片尺寸。
- 已查看[横向直边插点](assets/insert-verification/insertion/insertion-connected-forward.png)、[纵向直边插点](assets/insert-verification/insertion_vertical/insertion-connected-forward.png)、[未连片段补接](assets/insert-verification/insertion/insertion-unconnected-bridge.png)。
- TypeScript/Vite构建通过：[日志](assets/insert-verification/build.txt)，既有3Dmol eval/大包提示不属于本轮新增。
- [Demo保护](assets/insert-verification/demo-protection.json)全目录内容哈希不变；正式联动参数未修改。原用户图[已归档](assets/insert-edge-user-request.png)。

## 边界

浏览器使用正式React/HTTP和隔离SQLite，全部API只重定向测试服务；当前MySQL测试只用随机目标，未替用户重写真实谱。复用既有点字段，无新API/表。未修改幅值依据、科学定义或其他计算门槛，也未重新加入高频端核对。

只在明确原直边时替换该边，不凭空间距离自动删整段路径；普通吸附连接仍按原逻辑处理，原有复杂/闭环曲线不会被自动科学采纳。旧URL恢复问题仍独立。本轮无部署/推送，Spec远程链接仍待推送后验证。

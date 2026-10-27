# 正式异常坐标定位验收

日期：2026-10-27。用户“继续”确认本轮Issue与Spec草案；对应FR-055至057、SC-031至032。

## 实现与证据映射

- FR-055/057 → backend/spectra/topology.py：与重算共用稳定ID连线图；迭代DFS判断分量、环内回边及分叉，O(V+E)，不按距离自动合点。每条诊断至多两个坐标，前端每页12条。
- FR-055 → quality.trace_diagnostics[kind]：诊断随本轮不可变run返回；λ/ωlog相同原因合并，公开读取移除内部点诊断；人工保存重置派生值。旧运行保持原样，点击重算才生成诊断。
- FR-056 → TraceDiagnostics、SpectrumDetailPage、SpectrumManualEditor、SourceCanvas：传曲线和稳定点ID，服务器核对版本，客户端检查点存在；一次性400%居中，表格/坐标/高亮同源。普通选点及之后拖动不强制重新居中。
- SC-031/032 → test_spectra_recalculate.py、spectrum-diagnostics.test.tsx及正式浏览器脚本。

## 验证结果

- 正式前端57项通过（原54项及3项诊断交互）。首次新增测试使用了当前Vitest未提供的断言，已改用次数和参数两条断言并通过。
- 后端113项通过、2项MySQL行锁测试在SQLite中跳过，覆盖缺口/孤立/闭环/分叉、真实环内坐标、旧点ID适配、长链无递归、非零距离不自动连接、公开过滤和保存失效。
- [当前MySQL](assets/diagnostics-current-mysql-validation.json)61项通过；原16集合/56运行逐行哈希及数量不变，无测试残留，不建库/表、不执行全表清理。
- [正式浏览器7场景](assets/diagnostics-browser-validation.json)通过，所有API重定向本次8191测试服务，真实React/HTTP/SQLite存储，无业务API写入。覆盖实际点击、编辑器目标居中/选中、返回无写入、闭环定位、删除撤销重做/保存重算、Sc分波独立定位、390px布局及旧诊断版本409。
- 浏览器首次发现React严格模式重复effect清除了定位后的视图；修正初始化焦点标记后重跑7场景全部通过。已查看[诊断列表](assets/diagnostics-issues.png)、[孤立点居中](assets/diagnostics-isolated-focus.png)、[窄屏定位](assets/diagnostics-mobile-focus.png)，目标点及坐标可见。
- TypeScript/Vite构建通过，既有3Dmol eval/大包提示不属于本轮引入。
- [20000点计时](assets/diagnostics-performance.json)：一次本机完整图诊断约24毫秒，说明核心遍历成本，不代表整页响应性能。
- [Demo保护](assets/diagnostics-demo-protection.json)：所有文件前后内容哈希一致；用户调参未修改或纳入提交。

## 用户当前数据边界

首次只读调查第20版有392点、5个分量（4条开放片段和1孤立点），没有闭环。实施过程中用户继续编辑，第22版只读复核变为352点、1个分量、无拓扑问题：[读取记录](assets/diagnostics-current-readonly.json)。不把旧诊断当作最新数据；本轮未对用户业务谱发起重算、删除或保存。一个连通分量只证明拓扑连通，不保证幅值/频率满足所有科学积分条件。

[本轮用户截图](assets/diagnostics-user-request.png)归档；Issue/Spec远程链接仍待推送后验证。未部署、未推送；之前刷新旧详情地址的版本提示不在本轮修改范围。

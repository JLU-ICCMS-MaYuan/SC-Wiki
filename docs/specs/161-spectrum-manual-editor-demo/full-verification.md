# 正式谱编辑、重算、定位及版本恢复全面验证

日期：2026-10-27。测试基线：8f90f365及本轮新增测试。用户要求：“你来帮我彻底测试一下”。本轮不修改业务源码，不改变数据或科学判定规则。

## 结论

**核心编辑/重算/定位回归通过，但旧版本页面恢复体验未通过。** 截图中的整页红色版本提示可以稳定复现；不能以单元测试或特征测试成功来宣称已修复用户问题。

## 复现的问题

| 编号 | 触发条件与结果 | 原因和影响 |
| --- | --- | --- |
| V1 | A、B标签页打开同一谱；A保存或重算，B刷新→出现整页“谱版本已变化” | URL固定保存collection_version/run，读取的是数据库当前谱，二者不一致即隐藏详情；α²F和DOS都可复现 |
| V2 | 在V1错误页点击“重新读取”→读取成功但仍显示相同错误 | reload只重新GET，不同步URL；只有“打开最新结果”会更新地址 |
| V3 | 重算已提交，网络中断导致响应丢失→旧页面重试409，刷新后V1 | 服务端已有新run，前端未拿到新地址；当前没有成功状态恢复流程，不是数据丢失 |
| V4 | 原模块打开后，在别的标签页保存/重算，再切回原模块→链接仍是旧版本 | Provider只在提取busy时轮询，不在窗口焦点变化后刷新谱列表；手动“刷新谱状态”能更新链接且保留主表单输入 |

定位代码：SpectrumDetailPage.tsx的mismatch与错误栏；usePropertySpectra的reload；PropertySpectraProvider的busy轮询。V1/V2/V3有真实浏览器复现，V4有组件/路由特征测试和代码依据，不能宣称已在真实用户主表单浏览器中端到端复现V4。

[与用户截图一致的复现](assets/full-verification/final/version/version-stale-after-refresh.png)、
[重新读取后仍报错](assets/full-verification/final/version/version-reread-still-stale.png)、
[响应丢失后刷新](assets/full-verification/final/version/version-lost-response-refresh.png)。

## 正常路径与保护

- 当前地址版本未变化时刷新正常。同页编辑保存或重算成功后，地址升级到返回的新run/version，继续刷新正常。
- “打开最新结果”能恢复最新详情，不产生业务写入。旧链接重用会重现版本错误。
- 编辑器已经修改但其他标签页提交了新版本，旧保存返回409，编辑器内的未保存坐标保留，数据库不被旧版本覆盖。
- 请求发送前网络失败，不产生新run，当前页面可重试；请求已提交但响应丢失按V3记录。
- 错误材料身份被拒绝，不能为了避免版本提示绕开材料/曲线权限校验。
- 连续加点、8屏幕像素吸附、撤销重做、缩放后吸附、人工保存回读、零频摘要、DOS分波独立保存均通过。
- α²F独立λ/ωlog、相对尺度ωlog、DOS积分与3N比较分离、缺口拒算、编辑后积分失效/重新计算均通过。
- 问题坐标的闭环/分叉/孤立/断片区分、正确分波选点居中、删除撤销/重算更新、旧诊断拒绝误定位及390px布局均通过。

## 测试范围与结果

- 前端共58项：已有57项通过，新增V4测试使导航文件从26项变为27项，再单独验证通过。见[首次57项](assets/full-verification/frontend-tests.txt)、[导航27项](assets/full-verification/navigation-extra-tests.txt)。
- 后端113项通过、2项MySQL并发测试在SQLite跳过：[日志](assets/full-verification/backend-tests.txt)。
- 当前MySQL61项通过（含并发保存及重算）：[报告](assets/full-verification/current-mysql-validation.json)。现有16集合/57运行前后数量和逐行哈希一致；随机临时测试记录精确清理，不建库、建表或全表清空。
- 4套正式浏览器共42项正常路径/保护断言，以及3项浏览器缺陷复现。版本套件的acceptance明确为needs_fix，即使特征断言通过也不代表体验验收通过。最终记录见[套件汇总](assets/full-verification/final/browser-suite-summary.json)、[版本特征](assets/full-verification/final/version/version-browser-validation.json)、[编辑](assets/full-verification/final/manual/snap-production-browser-validation.json)、[重算](assets/full-verification/final/recalculate/recalculate-browser-validation.json)、[定位](assets/full-verification/final/diagnostics/diagnostics-browser-validation.json)。
- 正式TypeScript/Vite构建通过：[构建日志](assets/full-verification/build.txt)，既有3Dmol eval及大包提示仍存在。
- [Demo内容保护](assets/full-verification/demo-protection.json)：本轮未修改Demo或用户联动参数。

浏览器使用真实React源码与正式HTTP/SQLAlchemy路径，每套使用独立SQLite和来源文件；所有API被重定向8191测试服务，没有向用户业务API写入。当前MySQL验证使用临时身份/草稿依赖，不等价于真实登录端到端科学验收。

## 测试工具中纠正的两处问题

首轮汇总脚本误给人工编辑套件开启绝对密度DOS样例，旧用例输入18被正确限制到图框最大0.35，导致断言失败；恢复该套件所需像素DOS样例后再测。随后吸附脚本在工具提示改变画布高度后立即记录旧屏幕坐标，出现偶发等待失败；新增连续动画帧布局稳定检查后再记录坐标，未放宽8px阈值。最终按独立夹具完整重跑。这两项是测试配置/时序修正，不是业务修复。

可复跑命令（使用项目Python环境）：

```bash
/Users/mayuan/software/miniconda3/envs/sc-wiki/bin/python -m scripts.verify_spectrum_browser --output "/tmp/scwiki-browser-verification"
```

工具拒绝复用未知8191服务，失败也终止自己启动的服务；不重启用户开发服务。

## 当前真实数据只读核对

[读取快照](assets/full-verification/current-spectrum-readonly.json)：当前被检查α²F为第23版、352点、单连通分量，无拓扑问题；内存重新计算仍因幅值标定依据缺失不可用。这个科学条件阻塞与URL版本恢复问题独立。只读分析没有替用户填写依据、保存或重算数据库记录；后续用户编辑可能使此快照过时。

## 后续修复建议（尚未实施）

建议把无未保存编辑的详情读取与写入版本保护分开：同材料、同谱、同曲线的旧链接可加载最新结果并同步URL；重新读取应真正恢复地址；原模块只刷新谱状态，不重载用户主表单；响应丢失时先查询当前run确认提交状态。编辑器未保存内容、材料身份变化和历史查看仍保留明确保护。本轮只测试和记录，以上不是已完成行为，Issue保持开放。

# 实现与隔离验收

日期：2026-11-07。Issue [#225](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/225)。本次仅本地源码交付；业务库未迁移、未历史回填，未推送或部署。共享工作区其他任务改动不计入验证或提交。

## 来源与源码

验证源码为独立HEAD归档加本任务20项代码的投影。最初基线 `ef0035504d2df97a5fe93a30f978a4ceb0f54f64`；随后依次纳入已提交的#224依赖 `0f2681d5099cd8ab496a656512c5b48e0a68aeb8`、`94d6408bb0b8f5be396ecdae9888fc971972eff6`，20项代码SHA256不变，追加运行匹配、运行器、记忆及旧科学填写回归58项。[源码清单](assets/validation/source-manifest.json)记录20项代码及依赖SHA256；提交按该投影逐字节核对，不整文件收录并行科学表单修改。

四篇主PDF重新经既有GROBID正式提取67、48、37、59条，共211条；文件SHA256及结果见[真实验证回执](assets/validation/real-validation.json)。原PDF依据和人工标签见[原文审计](assets/reference-audit.json)。引文提取本身未改动；没有把旧科学字段提取冒充重跑。本次复用已组装的科学草稿，仅重跑引用支路及正式后处理。

## 需求验收证据

| 需求／任务 | 实际验证与结果 | 可查证据 |
| --- | --- | --- |
| FR-001/002、SC-001、T002/003 | 原始4篇211条，程序恢复6条真实边；公式计数、不同年份／作者冲突不直接匹配；错ID、漏答及非法协议失败留据 | [匹配与生命周期等58项](assets/validation/projected-final-python.log)、[标签](assets/reference-audit.json) |
| FR-002/003/004、SC-002、T003/004 | 保留原引文，仅受控缺损两条提取题名，真实LLM2一批核对；802输入＋103输出＝905 tokens；重复0新增调用；全站原模型恢复 | [真实回执](assets/validation/real-validation.json) |
| FR-003/006、SC-003、T004 | 独立MySQL真实迁移、工作稿保存、ready前匹配钩子、提交及批准；2条正式llm2记录新会话重读，全部6条公开边一致；SQLite生命周期和权限覆盖归档、源编号稳定、缓存防伪 | [真实回执](assets/validation/real-validation.json)、[生命周期回归](assets/validation/projected-final-python.log) |
| FR-005、SC-004、T005 | 真实Go→Python→MySQL、私有Vite；解析页链接target=_blank；1600及390px三列顺序、59条引文、右侧2命中／左侧1命中；所有者和两种管理员可读，他人403，刷新只读 | [浏览器回执](assets/validation/browser-validation.json)、[桌面](assets/validation/matching-desktop.png)、[窄屏](assets/validation/matching-mobile.png) |
| FR-007/008、SC-004、T006 | 默认2个有短标题节点；physics关闭、无动态曲线隐藏点、静置0次重画；两次拖动均保持；展开到4节点6直线，旧位置不变、新节点可见；刷新恢复2默认节点及坐标 | [浏览器回执](assets/validation/browser-validation.json)、[图谱](assets/validation/graph-expanded.png)、[Go专项](assets/validation/projected-go.log)、[前端2项](assets/validation/projected-ui.log) |
| FR-009、SC-004/005、T007 | 固定字段契约通过；四科学宿主form-contract 210通过；8渲染＋4漏红变异全部检出；生产构建通过；旧引用图／schema 6通过 | [字段](assets/validation/projected-field.log)、[表单](assets/validation/projected-form.log)、[变异](assets/validation/projected-mutation.log)、[构建](assets/validation/projected-build.log)、[旧引用图](assets/validation/projected-citation-regression.log) |

真实6边为271→1204、271→1208、271→1429、1204→1208、1429→1204、1429→1208。程序直接恢复本组关系；真实模型验证使用受控题名缺损触发，不能描述为原始211条都需要AI。此前本地4B与LLM2对照见[对照回执](assets/model-comparison.json)，费用仅比较tokens，未估算金额。

## 既有基线与环境问题

- 全量Go出现旧 `TestApplyPaperEvidenceArchivesManualReasonInReviewTransaction` 失败，sqlmock仍期待删除 `scientific_evidence_checks`。独立旧HEAD同名同错，见[本轮](assets/validation/go-all.log)与[基线](assets/validation/go-head-baseline.log)。图谱专项通过，不宣称全量Go通过。
- 系统Node26.9.0内建localStorage影响jsdom，旧HEAD的review-actions同样12失败，见[基线](assets/validation/node26-head-baseline.log)。改用已有bundled Node24.19.0运行本轮完整表单210项通过，未改断言或放宽超时。
- 旧科学重写套件在独立空MySQL建立阶段调用 `upgrade head`，因已有 `20261102_0160` 与 `20261102_0204` 多头而13项setup error；#225沿0204增加0225，并未新增分支。独立旧HEAD同样13项setup error，见[本轮](assets/validation/rewrite-fresh.log)与[基线](assets/validation/rewrite-head-baseline.log)。未将初次无配置时13 skipped计为通过，也未为本任务擅自合并News迁移头。

## 迁移、清理与边界

迁移只在独立MySQL执行，既有211条内容摘要保持。存在依据时降级明确拒绝丢弃。三个隔离服务已停止、独立库已删除、17个本轮临时对象已清理，业务四篇及211条引用摘要复核不变，见真实回执末尾。临时JWT／私有runtime未归档。

当前业务库旧匹配仍保持原状，不能把隔离库6边写成用户业务页面已修好。业务升级与历史回填需在明确目标环境下单独执行。GROBID仍有一段Funding被当引文；211代表已解析条目，不承诺参考文献完整提取。本次不新增丢弃或重编号规则。

未重跑整篇科学提取，不据此认定全站科学流程或远端CI通过。AI自动生成图谱标题策略仍排除本次；未添加图谱高亮或额外人工审核轮次。Issue远程Spec链接未发布，保持OPEN，见[实际远程核验](assets/validation/remote-spec-link.json)及Issue最新交付记录。

文本日志归档时仅去掉ANSI颜色控制符及行尾空格，内容与错误保持；[日志清单](assets/validation/log-format.json)保留原始与可读副本的SHA256。原始模型失败回执和原图未改写。

## 后续本机迁移（2026-11-09）

用户指定本机原生环境后已执行0225迁移，74张旧业务表数据及211条引用内容不变，Python/Go就绪通过。见[本机迁移验收](native-migration-20261109.md)；上文的“未迁移”描述保留为2026-11-07首次源码交付时的事实，不代表当前本机状态。未做历史回填，Y-H测试由原聊天继续。

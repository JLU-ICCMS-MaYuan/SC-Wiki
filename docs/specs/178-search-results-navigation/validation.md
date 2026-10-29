# 文档与实现验收记录

日期：2026-10-29；Issue：[＃178](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/178)。下方先保留文档阶段记录；最新本地实现与验收见本记录末尾，旧“未完成”是当时状态。

## 已执行

- GitHub CLI重新读取Issue：编号178、OPEN、唯一type:feature；正文含本地Spec路径及远程待验证说明。与本地Spec分别核对完整用户正文和批注，共44段引用逐字匹配临时输入副本。
- 6张原PNG原字节归档；归档后重新读取，逐张SHA256及尺寸核对，再用sips实际解码，全部成功。详见[图片索引](assets/images.json)。临时重解码副本不是权威原图。
- 本Feature Markdown的22个相对文档／图片链接全部存在。这里只验证本地相对链接，未声称远程Spec链接已可访问。
- FR-001～020、SC-001～009编号连续无重复；Tasks的T001～021连续且全为未执行。逐段核对Plan和Tasks映射覆盖需求、默认同页切换与导航例外、身份／结构边界及回归。
- 对照Spec模板逐栏检查，未使用模板占位。原话与AI上下文分开；原先询问两个入口、后续主动保留及旧Tc表格的删除取舍均保存。
- #56 FR-004及#59 FR-011定向替换固定上传返回，并追加历史原文／取代说明；#49和#142追加后续需求及尚未实施声明，共4个旧Spec，未改Overview当前事实。
- `git diff --check`通过。提交前仅暂存本Feature规划、原图和上述4个干净旧Spec；共享工作区已有#177及其他文件不纳入。

机器核对结果：[assets/document-checks.json](assets/document-checks.json)。文件／链接存在只能作为机械检查证据，需求完整性以原文和上列实质审查为准。

## 未完成与后续

- 新技术Plan尚未获得用户对其内容的审阅确认，T001保留未执行；需求采纳答复不冒充技术设计确认。
- 远程Spec文件尚未推送，双向远程链接未核验；不得自行push解除文档门。
- 没有改业务源码、接口、迁移、运行服务或业务数据；没有执行功能测试、MySQL集成、浏览器或表单合同检查，所有SC与实现任务仍待交付。
- #15旧表格DOI事项只关联说明，未更新或关闭该Issue；其取舍待本Feature实际实施时同步。
- Issue保持OPEN，未把新功能写入Overview或宣称本地实时环境／阿里云已更新。


## 2026-10-29：本地实现与验收

用户已回复“开始实现”；以下结果更新前一轮文档阶段状态。本次实现沿已确认的Spec、Plan及原话，不重新解析PDF，不调用AI，不写业务科学数据。

### 实现结果

- 新Go端点直接查询状态及完整结构来源，按论文／状态去重、统计和分页；不是前端去重一页旧Tc记录。默认论文，同页切换；8状态／12Tc仅计8状态。无Tc状态、无状态模型来源、当前批准revision和同状态条件匹配有独立查询证据。
- 旧搜索Tc明细与局部详情退役；按状态显示压力、报告空间群、优化方式。独立结构服务端先过滤已关联项再计数；新请求的材料家族使用当前论文关联，Tc／图表变化不重查无关结构。
- 原生新标签链接遵守矩阵，URL恢复视图／分页；详情来源校验拒绝外部跳转并保留编码关键词。返回元素配置也保留原选择和模式。
- 评论组件与体系入口移除，旧评论读取返回410，普通写入继续拒绝，管理列表和通知不公开退役评论；保留历史表记录、AI问题／答案和审核意见。

### 实际检查

| 检查 | 实际结果与范围 |
| --- | --- |
| 前端受影响模块、账户及认证 | 12文件115项通过，含同页切换、原生链接、合法return、迟到响应、无关结构请求不重发及原选择恢复；[日志](assets/frontend-regression.log) |
| Go查询及社区 | 7项通过；[日志](assets/go-regression.log)。全量handlers另有下述既有失败，不能宣称全量通过 |
| 隔离MySQL | 集合、去重、分页、当前revision、无Tc／无状态模型、相同300GPa优化条件，以及41状态真实多页用例通过；[日志](assets/mysql-regression.log) |
| Python结构路径 | 19项通过，涵盖independent_only在计数前生效、当前家族筛选及既有来源／读取／导出；[日志](assets/structure-regression.log) |
| 强制表单合同 | 79项通过，含四类宿主；[日志](assets/form-contract.log) |
| 变异检查 | 四宿主8项预期故障均检出；[日志](assets/mutation.log) |
| Chrome真实React路由 | 13场景通过：新结果标签、默认论文、同页8状态、旧表退役、刷新、来源返回、结构新标签、浏览器后退、390px、独立模型来源、非法return、第2页返回、键盘切换；[请求与结果](assets/browser.json) |
| TypeScript及生产构建 | npm run build --prefix frontend通过；既有包体积提示保留，[日志](assets/build.log) |

浏览器主查询走正式Go Handler和隔离MySQL；论文／结构详情内容和独立结构列表响应是隔离夹具，结构持久化及CIF导出由Python测试另证。未重提真实论文或宣称整篇科学验收。浏览器在匿名上下文运行；角色入口／认证以宿主测试及既有Auth同步回归覆盖，不冒称四身份真实浏览器全部重跑。

### 首先失败的证据与固定数据

新双视图宿主用例在旧实现上失败：找不到“按论文”切换，见[failure-before.log](assets/failure-before.log)。修复后该交互及迟到响应／分页回归通过。Go／MySQL固定H-La-Sc的1论文8状态12Tc；独立LaSc2来源及Fe的41状态为额外用例，不是业务库常量。

### 扩展测试既有失败

独立Git归档源码复现相同失败，见[逐项比较](assets/baseline-comparison.json)：

- 前端4项：paper-detail-form-parity的材料分类、压强单臂、数值槽3项；英文巡检的TcPredictPage 1项。
- 全量Go handlers 1项：TestApplyPaperEvidenceArchivesManualReasonInReviewTransaction。

这些失败未被删除、跳过或放宽断言，本次通过数不包含它们。旧Tc局部详情测试按退役需求迁移到新结果或正式论文阅读，原换行、权限和重试行为仍有实际宿主测试。

### 截图与源码边界

- [默认论文视图](assets/implementation-papers-desktop.png)
- [材料状态桌面](assets/implementation-states-desktop.png)
- [材料状态390px](assets/implementation-states-mobile.png)

截图是隔离夹具的实现验收图，与原六张用户截图分开。源码字节及基线见[source-manifest.json](assets/source-manifest.json)，各项计数见[implementation-checks.json](assets/implementation-checks.json)。已同步Overview、根README、表单清单和旧Spec约束，并在[#15评论](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/15#issuecomment-6498567247)记录旧表格范围被#178取代；未关闭#15。

除隔离验证外，额外只读核对当前本地原生实时环境，现有Go watcher已经自动加载新端点；La-Sc-H精确查询实际返回1论文／8状态，三元独立模型为0（已关联模型不重复），二元La-Sc独立模型为1。记录见[live-local-smoke.json](assets/live-local-smoke.json)。没有手动发布或重启业务Go进程，没有业务写入；未推送、未操作阿里云。远程Spec实际链接未核验，Issue保持OPEN。临时预览进程已停止，测试数据库和转码／安装产物按本次范围清理，业务数据及原始草稿保持。

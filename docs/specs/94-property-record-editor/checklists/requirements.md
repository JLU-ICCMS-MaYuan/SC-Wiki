# 需求质量检查表

- [x] CHK001 标题隐藏版本与内部版本保留边界明确。[FR-001]
- [x] CHK002 单文本框、六方面弱约束及空值语义明确。[FR-002、003]
- [x] CHK003 条件逐记录归属、旧信息及证据保留已定义。[FR-004、数据模型]
- [x] CHK004 默认展开、独立折叠和只读交互明确。[FR-005、006]
- [x] CHK005 每项 FR/SC 均映射到实现与可观察验证。[Plan]
- [x] CHK006 唯一 Tc 入口、无独立原始记录、响应式断点和条件行顺序已确认。[FR-007、008]
- [x] CHK007 零值、临时输入、清空、范围及保存阻断规则明确。[FR-009、010]
- [x] CHK008 共享入口、稳定身份、核对兼容与隔离数据验证可追踪到任务。[FR-011、SC-004～006]
- [x] CHK009 最新值覆盖旧 raw，零值、范围、文本、布尔、新建只填一次、清空不回填及历史边界已明确。[FR-008、009、澄清记录]

## US5 增量

旧 CHK006 的多列断点由 FR-013 取代。

- [x] CHK010 用户完整原话与最终 Demo 留档，两张原图可读取且哈希、尺寸和取色可复查。[Spec 原始需求、assets/images.json]
- [x] CHK011 已认可的单行、前置参数、两组同色无边框 Tc/μ* 及内部逆向端点映射覆盖 FR-012～017。[用户“认可，开始落地”、Spec、Plan]
- [x] CHK012 参数可空、零值、临时非法输入、旧包装及扩展证据保留可验收。[tc-paired-parameters.test.tsx、test_tc_paired_parameters.py、quickstart]
- [ ] CHK013 本次更新后的远程 Spec 双向链接验证；本地未推送，不将旧版链接当作新版本证据。

## US6～US9 实施范围核对

- [x] CHK014 用户认可整合 Demo 并明确授权全部落地，完整原话追加至 Spec，Issue 同步；未把附件指令当作用户指令。[Spec 最新实施基线、Issue #94]
- [x] CHK015 FR-018～034 已映射组件、版本化数据契约、T020～027 和 SC-019、022～025。[Plan 映射、contracts/record-form.md]
- [x] CHK016 不同凸包依据、ZPE 三态、未知值和谱权限依赖边界明确，主表单和人工草稿失败路径有行为验证。[quickstart、热力学/谱导航/人工证据测试]
- [ ] CHK017 #137 目标环境谱 API/数据库就绪与真实论文谱的独立详情验收；未执行业务迁移，保留外部依赖。

## US10 模块默认折叠

- [x] CHK018 用户原话、四模块默认折叠和原记录层折叠的区别已明确。[US10、FR-035～036]
- [x] CHK019 保留未保存输入、已有顺序兼容/删除工具栏独立、只读和仅谱模块均有交互覆盖。[property-module-collapse.test.tsx、property-spectra-navigation.test.tsx]

## US11 取消模块上下移动

- [x] CHK020 #90 原排序实现与 #94 当前迭代入口已核查，新原话及 IMG-006 完整归档；最新要求取代手动排序交互。[US11、assets/images.json]
- [x] CHK021 无上下移动入口、已有顺序兼容、默认折叠及删除限制已覆盖，未引入固定重排或迁移。[FR-037～038、相关交互回归]

## US12 两行布局设计

- [x] CHK022 新原话、来源类型与结构层两次明确答复、IMG-007 已留存；历史 mixed 语义由 #50/#84 证实。[Spec US12]
- [x] CHK023 七字段首行、条件核处理第二行及局部试填恢复已通过浏览器演示验证。[assets/material-state-two-row-validation.json]
- [ ] CHK024 用户评审本轮 Demo；精确选项命名、多结构绑定及正式实施仍未确认，本轮不进入业务实现。

## US13 固定高度与 mixed 退役

- [x] CHK025 最新用户原话完整保留；#109 的自然增高条款被明确标作旧设计，与最新固定框高要求不混淆。[US13]
- [x] CHK026 固定高度、第三行独占、水平多标签/长标签、窄屏和类型显隐有浏览器观测依据。[assets/material-state-three-row-validation.json]
- [x] CHK027 mixed 已从当前方案全面退役，旧“以后兼容”结论被覆盖；当前 Demo 验证与真实业务退役执行分开。[FR-044]

## US12/US13 正式实施

- [x] CHK028 最新单份几何原话完整保留，FR-045～046/SC-035 与模型、契约、T042 对齐；复用 #49/#77，明确修订 #32 同卡多优化结构。
- [x] CHK029 浏览器三入口证实七字段、三行、53.125px 固定框高、17 长标签、736px、类型显隐、保存刷新及只读核处理；结果见 quickstart 与 assets/state-implementation-browser.json。
- [x] CHK030 隔离 MySQL 证实保存/返修/导出与 CHECK/唯一约束；迁移拒绝无损边界 5 项通过，不删除附件和 Evidence。
- [x] CHK031 目标业务实例实际迁移及真实 API 验收：见 assets/state-local-migration.json，完整 schema 核验、三份草稿 GET200、非法类型/核处理/多结构 PUT400 且前后草稿相同，服务恢复。
- [ ] CHK032 新版远程 Spec 链接：未推送，继续保持待验证。

## US17 记录操作 Demo

- [x] CHK033 完整原话与 AI 判断分离，已有 #94 为 OPEN 且唯一 `type:feature`；没有新增同范围 Issue。[Spec US17、GitHub 本轮查询]
- [x] CHK034 明确复制实际行为与有限使用价值，设计已获认可但未写成已实现行为；US15 的 DOS 清理未混入本轮。[Spec US17、Research US17]
- [x] CHK035 同行删除、局部滚动、只读、目标隔离和试填保留有浏览器观察依据；只证明独立 Demo。[SC-043～044、assets/record-actions-demo-validation.json]
- [x] CHK036 IMG-012 从归档位置解码并验证尺寸和 SHA-256，原文件与截图派生材料分开保存。[assets/record-actions-images.json]
- [x] CHK037 用户已查看并认可本版完整 Issue 追加草案与 Demo，实际答复“认可设计并同步 #94，暂不落地”；#94 已追加完整获批正文及最新答复，读回核验保持 OPEN、唯一 type:feature，SC-045 的设计确认和同步部分已满足。[Spec US17、GitHub #94 US17]
- [ ] CHK038 正式实施授权及四模块集成验收已完成；远程 Spec/附件链接仍未推送验证，合并检查项保持未完成，不关闭 #94。

## US17 正式实施基线

- [x] CHK039 用户已认可 Demo 与完整 Issue 正文，最新“开始落地！”明确授权 US17 实施；不包含 US15/US16 的数据方案。[Spec US17 正式实施授权]
- [x] CHK040 FR-056～059 阶段解释、SC-049～050、主行责任、删除键和既有数据合同已对齐；映射到 T063～066。[Spec、Plan、Research、data-model、contracts/record-form]
- [x] CHK041 四模块共六种记录在实际组件浏览器中宽/窄容器对齐中心差均为 0 CSS px，字段区局部滚动；只读与目标键盘删除通过。隔离候选 7 份/100 项回归及 TypeScript/生产构建通过。[SC-049～050、assets/record-actions-implemented-validation.json、quickstart 正式实施验收]


## US18 简洁结构折叠

- [x] CHK042 用户完整原话、IMG-015、历史 #103 规则、Demo 与最新“认可。开始”均留存；确认默认收起和正式实施，#94 已追加获批草案并读回核验 OPEN/唯一 type:feature。[structure-collapse-demo.md、GitHub #94]
- [x] CHK043 FR-066～068 / SC-053～055、Plan/Research/展示合同、T071～073 对齐；当前结构 hash 与来源对应，结构/派生表示保存合同不改，#103 保留历史并增加新规则指向。[structure-collapse-demo.md 正式实施基线]
- [x] CHK044 正式共享组件及真实 3Dmol 在1280/390px、首次展开、旋转/缩放像素保留、候选/晶胞/格式/坐标保留、来源及焦点、只读、空态和新增候选行为均通过；独立源码58项回归、TypeScript/生产构建通过。[assets/structure-collapse-implemented-validation.json]
- [ ] CHK045 新版远程 Spec/附件：尚未推送，远程链接待验证，不据本轮验收关闭 #94。


## US19 添加入口底部设计

- [x] CHK046 原话和IMG-016完整留档，AI解释与原文分开；复用OPEN/唯一type:feature的#94，关联既有模块和谱展示合同。[module-add-bottom-demo.md、GitHub只读查询]
- [x] CHK047 两状态、空态、谱展示、只读、键盘、保持输入与390px的Demo验证有可复查记录。[SC-056～057]
- [ ] CHK048 用户评审完整追加草案和Demo，远端Issue同步及正式实施尚未授权；远程Spec链接待推送验证。[SC-058]

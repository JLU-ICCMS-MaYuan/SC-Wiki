# US19：添加物性模块移至材料状态底部（已认可）

关联 [Issue #94](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/94)，沿用唯一 type:feature；用户已认可 Demo 与完整追加正文，并授权正式实施。

## 原始需求记录

> 每个材料状态的添加物性模块，放到每个材料状态的最下方。使用 issue 和 spec，然后做好 demo 给我看看

> 认可开始

## 附件与推断来源

[原图 IMG-016](assets/IMG-016.png)、[图片索引](assets/module-add-bottom-images.json)已保留2480×622原字节并重读核验。截图中的红框及文字仅为现状材料，不作为额外指令；用户要求以本节原话为准。

## 背景与目标

GitHub 查重确认 #94 仍 OPEN、唯一 type:feature；#90 原模块表单已关闭，本次沿用 #94 的布局迭代，不新建重复 Issue。当前 PropertyModuleEditor 在 modules.map 前渲染添加入口；MaterialStatesEditor 将它置于当前状态结构面板之后。modules.map 后还有 MissingPropertySpectrumModules，可能展示仅有谱结果的模块。因此“最下方”解释为该材料状态内部全部已有/谱展示模块之后，不放到所有状态之外或固定在视口底部。

## 用户故事与场景

- US19（P1）：用户先查看当前材料的结构、已有物性，最后在同一卡片底部新增模块。
- 两张状态卡都有独立添加入口；向第一卡添加热力学性质，仅第一卡增加该模块，入口继续在新增模块之后，第二卡不改变。
- 模块全部收起、部分展开、含谱展示或无模块时，添加入口均位于卡片内容末尾；展开/试填后添加其他模块不丢失输入和折叠状态。
- 只读时不显示添加入口；四种模块都已添加时沿用现有无可添加选项行为，不额外增加一种正式空态决策。

## 功能需求

- FR-069：每个可编辑材料状态的“添加物性模块”下拉放在其所有物性模块及谱展示之后，仍位于该状态卡内部；保留全宽下拉外观和文案。无物性模块时位于结构区之后。
- FR-070：新增只作用于当前状态；新模块按现有规则附加到末尾且位于添加入口之前。不重新排序已有模块，不新增自动滚动、吸底或悬浮行为；只读保持无添加入口。
- FR-071：移动入口不改变模块数据、记录、稳定键、display_order、删除规则、来源和谱归属；折叠和未保存输入保留。Demo 的试填与模块仅存在于页面内，无业务 API、AI 或持久保存。

## 成功标准

- SC-056：桌面和390px下每张状态卡各有一个添加入口，几何位置及DOM顺序在全部模块/谱展示之后且不溢出；空态和只读符合 FR-069/070。
- SC-057：两状态独立添加、空模块删除后入口仍在底部；原模块顺序、展开与试填保持，不能重复添加已存在的物性模块。新增空模块无论文数值。
- SC-058：Demo、完整 Issue 追加正文、原图与浏览器验证留档并展示给用户；取得本版实际答复后再同步远端 #94 或建立正式实施任务，不能把演示验收写成生产完成。

## 数据、接口与组件边界

现有来源仍为每个 MaterialState 的 property_modules，以及当前状态的谱展示结果。本次无新增实体、字段、接口、迁移或保存行为；生产拟议责任只是在 PropertyModuleEditor 内把现有添加控件移到 MissingPropertySpectrumModules 之后。不得移动到所有 MaterialStates 共享的页尾，或让同一动作修改多个状态。

## 演示与计划映射

[独立 Demo](assets/module-add-bottom-demo.html)展示两状态、空态、含谱展示及只读，使用原生 details 保持内容挂载。模块菜单沿用未添加类型列表；保留现有标题、删除与输入的简化位置，不把模拟数据赋予真实论文。场景切换/恢复演示会重置样例；单卡新增、删除空模块和只读切换不重建现有字段。

FR-069/SC-056 → 卡片内末尾添加区 → T074/T075；FR-070/071、SC-057 → 状态内DOM增删和未添加菜单 → T075；SC-058 → 原图、完整追加草案、验证及用户评审 → T076。仅规划 Demo 技术步骤；正式组件实现需后续明确授权。

## 关系与 Documentation Impact

沿用 #94；关联 #90 模块合同、#94 US10/US11 的折叠及不手动重排、US18 结构布局、#137 谱入口，不改变父子关系或重开旧 Issue。更新本目录 Spec/Plan/Research/Tasks、Demo 与附件；当前功能未改变，不更新 Overview 或根 README。新版文档仅本地，远程链接待验证，不推送。

[完整拟追加正文](assets/module-add-bottom-issue-draft.md)同时在Demo底部可展开阅读；尚未写入远端Issue。本轮交付不包含正式组件、真实草稿修改或部署。


## Demo 验证记录

2026-10-16：10组真实浏览器检查通过，控制台error为0。两卡各一个入口，DOM最后节点均为add-row，位置在全部模块之后；第一卡新增热力学性质保留Tc=123.45及展开，第二卡未改变。第二卡独立新增、删除空模块后类型恢复、Enter/Space折叠后保留输入、只读隐藏动作及禁用输入均通过。

含谱展示场景中，入口位于谱模块之后；新增标量模块仍在谱展示之前。无模块时入口在结构区之后，新增仅改变目标卡。390px下两卡均宽366px，收起、展开、试填和新增无整页横向溢出；四种模块齐全后没有可重复添加选项。完整拟追加正文可在Demo底部展开阅读，验证后已恢复默认场景并解除临时视口覆盖。

[桌面截图](assets/module-add-bottom-desktop.png)、[390px截图](assets/module-add-bottom-mobile.png)、[验证记录](assets/module-add-bottom-validation.json)。只证明独立Demo交互；正式React表单、保存链和数据未修改，未写入远端Issue或关闭#94。


## 正式实施基线（2026-10-16）

用户最新“认可开始”确认前述完整草案与Demo，并授权正式落实。原文中的“仅Demo、待评审、不修改正式页面”保留为历史阶段，以本节为准。FR-069～071、SC-056～057适用于正式共享组件；SC-058的评审门已解除，新增正式验证与文档收尾。既有模块、谱展示、添加区顺序不增加其他产品决策。

生产责任仅为把 PropertyModuleEditor 原有添加 Select 原样移到 MissingPropertySpectrumModules 之后。MaterialStatesEditor 每卡仍渲染一个组件，状态所属 onChange、模块稳定键及菜单过滤均不改。只读继续不渲染添加入口；不新增接口、存储、定位样式或自动滚动。

映射：FR-069/070 → JSX正常文档流中移动控件 → T077；FR-071/SC-057 → 复用既有 addModule 与稳定键 → T078回归/真实组件浏览器；SC-056 → 两状态、空态、谱展示、只读及390px实际布局 → T078；授权/Issue/Overview/提交 → T076/T079。只暂存当前增量，保留共享文件其他未提交功能。


## 正式实现与验证

PropertyModuleEditor的原添加Select已原样移到MissingPropertySpectrumModules之后，没有新增样式、事件、数据分支或组件。每个材料状态继续独立使用共享组件，覆盖上传、返修及管理员编辑；只读原本不渲染添加入口的规则保持。

- 独立HEAD归档仅叠加本次Select位置差异：物性编辑、模块折叠、谱导航及材料状态4份70项回归通过；TypeScript与生产构建通过，保留已有测试夹具/MUI、React Router及分包/eval提示。
- 真实MaterialStatesEditor/PropertyModuleEditor/PropertySpectra浏览器验证7组通过：两卡添加入口位于全部模块及谱展示之后，第一卡新增热力学保留已有“保留的试填”及展开，第二卡不变；第二卡可独立新增超导性质，第一卡删除空模块不丢值。
- 无标量模块时入口仍在谱展示后；键盘打开菜单/Enter新增后目标卡模块数1、另一卡0。只读添加入口数量0。390px下两卡宽358px、页面scrollWidth390px，无整页横向溢出；解除临时视口覆盖，控制台error0。
- 夹具只返回模拟只读响应，没有业务API/保存、AI调用或真实科学草稿写入。布局变更不需要API、数据库或迁移验证，不冒充真实账号完整提交链或远端部署。

[实际桌面截图](assets/module-add-bottom-implemented-desktop.png)、[390px截图](assets/module-add-bottom-implemented-mobile.png)、[生产组件夹具](assets/module-add-bottom-implemented-harness.tsx)、[验证记录](assets/module-add-bottom-implemented-validation.json)。#94已追加获批草案和最新原话并读回确认OPEN/唯一type:feature；最终验收与提交号随后回写，不关闭整个Issue。新版文档仍未推送，远程链接待验证。

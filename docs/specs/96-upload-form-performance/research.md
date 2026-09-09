# 研究记录：上传解析记录表单性能修复

## 现状证据

1. [UploadTaskEditor.tsx](../../../frontend/src/components/UploadTaskEditor.tsx) 的 `changeDraft` 每次调用都会更新完整 `UploadDraft`；材料状态回调在第 626–640 行把完整数组继续传给共享编辑器。
2. [MaterialStatesEditor.tsx](../../../frontend/src/components/MaterialStatesEditor.tsx) 在 `states.map` 中直接创建每张卡片，晶系变化时每个状态的空间群选项都会重新筛选；空间群 Autocomplete 的 `onInputChange` 逐字符更新状态数组。
3. [PropertyModuleEditor.tsx](../../../frontend/src/components/PropertyModuleEditor.tsx) 和 [SchemaDrivenRecordForm.tsx](../../../frontend/src/components/SchemaDrivenRecordForm.tsx) 当前没有渲染记忆化边界。记录变化会重新执行客户端校验和动态 Schema 构造。
4. `PropertyModuleEditor` 的定义绑定 effect 依赖完整 `modules` 引用；记录编辑会创建新数组，并对已有定义再次调用 `setBoundDefinitions`。
5. 自动保存由 5 秒定时器触发，选项事件本身不等待 API；因此主要延迟来自同步渲染和计算，不是保存请求。

## 性能反馈环

使用临时 Vitest + Testing Library 探针挂载真实材料编辑器并实际打开晶系下拉。5 个材料状态的单次修改测得约 65.83 ms；更大的完整上传编辑器在 30 个状态场景约 461 ms。探针只用于诊断，已删除，不作为产品测试提交。

## 决策

### 决策 1：用记忆化的材料状态卡片隔离渲染

**理由**：状态数组更新时未修改项保留原对象引用；以 `state` 引用为比较依据即可跳过其余卡片的 MUI 树渲染。卡片内部仍通过父级回调提交完整状态数组，不改变数据所有权。

**备选方案**：引入全局表单状态库或虚拟列表。前者增加依赖和迁移成本，后者会改变现有折叠、错误定位和无障碍 DOM 语义，均超出本 Issue。

### 决策 2：空间群输入与草稿提交分离

**理由**：自由输入不需要每个字符都改变科学草稿；本地输入值可保持输入法和光标体验，选择候选或失焦时再提交最终字符串。

**备选方案**：仅对父级更新做 debounce。它仍会在输入期间周期性重渲染，并可能让受控输入值滞后，因此不采用。

### 决策 3：缓存纯计算并抑制重复定义绑定

**理由**：空间群过滤、Schema 合并和 `validateRecordClient` 都是由输入引用决定的纯计算；定义绑定只需在身份变化时写入，避免 effect 产生额外状态提交。

**备选方案**：删除前端校验或把定义绑定移到后端。这样会破坏现有即时错误提示或提交前定义版本契约，不采用。

## 风险与回滚

- 卡片 `React.memo` 比较函数若遗漏影响展示的 props，可能出现旧值；测试覆盖状态值、折叠状态、错误和目录加载态。
- 本地输入若未处理 `blur`、`clear` 和候选选择，可能造成草稿丢失；测试覆盖三条路径。
- 所有改动均为前端可逆代码，不涉及迁移；回滚只需恢复本 Feature 提交。

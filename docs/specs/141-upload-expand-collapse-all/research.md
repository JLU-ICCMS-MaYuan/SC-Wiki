# 技术研究

## 当前事实

- `UploadPage.tsx`持有顶部固定操作栏；`UploadParsingDetail`下的编辑器渲染材料状态。
- `MaterialStatesEditor.tsx`已有两颗按钮及局部`collapsedStates`，外层使用MUI Collapse且不卸载内容。
- `PropertyModuleSection.tsx`用原生details维护展开状态；模块内部记录使用独立Accordion。
- 材料状态的晶体结构使用独立按钮维护展开状态，其他详情入口也有相似模块标题；选择范围必须限定在当前物性模块区域。

## 决策及理由

1. 用一个仅传递DOM容器的局部Context和React Portal，将已有按钮放到顶部槽位；没有槽位的既有调用方继续原位显示。避免跨上传详情、编辑器多层传递同一操作，也不复制按钮和处理逻辑。
2. 同一处理函数更新材料卡片局部状态，并在当前编辑器物性区域内同步原生details.open。原生details原本就以DOM为展开状态来源，继续保留其原生单项交互；不通过重新挂载、改key或重置表单完成展开。
3. 不引入全局事件总线、业务草稿字段或持久化设置；不改变API和数据模型。
4. 顶部容器允许换行，两个按钮共用现有中英文字典；无状态或只读时禁用。

## 备选方案

- 多层命令prop：需要修改UploadParsingDetail、UploadTaskEditor和物性组件，增加无关转发职责，未采用。
- 查询整个document：可能影响其他编辑器、结构及弹层，未采用；仅使用当前编辑器内的物性区域。
- 只折叠外层：无法满足全部展开模块及重开材料后模块仍收起的验收。

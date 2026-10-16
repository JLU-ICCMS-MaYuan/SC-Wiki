# 记录表单契约

## AI 输出与数据传递

现有分段和汇总内部输出的每条实验 Tc 增加：

```json
{
  "result_kind": "experimental",
  "tc_method": "experimental",
  "tc_value_k": 4.2,
  "value_raw": "4.2 K",
  "experimental_conditions": {
    "description": "Resistivity was measured using a four-probe setup at zero applied field."
  }
}
```

缺失方向不补写。两条 Tc 各自携带条件，汇总不得仅因为同材料状态/同方法而合并。
既有转换生成 measured_tc 记录，把实验条件对象原样传递到 payload；
正式草稿 API 仍只使用 property_modules，不新增 tc_results 公共字段。

## 人工输入与校验

实验条件显示一个多行输入框，绑定 payload.experimental_conditions.description。
description 存在时必须是字符串；不要求六个方面齐全或单位数值化。错误定位到该字段。
老对象未编辑时不变，编辑后保留旧字段并更新 description；只读态禁用输入。

## 记录折叠

记录标题、下拉选项与只读标签不显示 vN，内部版本不变。
每条记录独立切换、支持 Enter/Space，折叠不调用数据 onChange。
默认展开，复制/新增记录展开；既有记录的状态随稳定键保留。
收起时显示结果摘要及服务端校验/定义加载错误提示。模块层原有折叠继续可用。

## Tc 紧凑输入

Tc 常用行顺序为名称、值类型、Tc 值（K）、代表结果复选框；实验条件独占下一行，
不再显示或要求填写原始值及原始单位。value_raw 随当前类型和值生成：数值为当前数字文本，
范围为下界–上界，文本为当前文本，布尔为 true/false。数字与范围的 unit_raw=K，其他为空。
清空数值将 value_number 设为 null、value_raw 设为空，不能回填旧值。
数值或范围不完整、负数、非有限数字及上下界倒置均在保存前报错。类型切换清理不适用规范值。
折叠摘要读取当前规范值，无规范值时显示待填写，不用旧原文冒充当前 Tc。
代表结果继续绑定 is_representative；唯一性由现有后端规则校验。
公共 API、Schema 版本和数据库字段不变；核对定位继续使用稳定身份和原字段路径。
服务器接受没有 value_raw 的有效 Tc，或覆盖与当前值不同的旧 value_raw/unit_raw；不能只凭
旧 raw 补足缺失的当前数值。普通物性的原始值契约不变，数据库中已有历史不批量修改。

Tc 核对的 editable_fields 不含 value_raw、unit_raw、canonical_unit，旧 raw 路径的红框仍定位
当前值。接受建议的预期内容随当前类型和值同步，不允许兼容文本与实际保存内容不一致。
科学计数法文本与表单保持一致，例如 1e-7、0.000001、1e+21；数字字符串与布尔值不能充当数字。

## 配对单行输入增量

本节取代上文常用行顺序：预测记录按 λ、ωlog、名称、值类型、Tc/μ*、Tc/μ*、代表结果排列。范围有两组，数值有一组；所有输入保持一行，宽度不足时仅行内滚动。标签只显示 Tc、μ*，相同 #F4F3FF 分组底色无外边框。测量范围同样无上下界标签，但不增加 λ/ωlog/μ*。

两组写入时以 Tc 端点排序，Tc 小端与 μ* 大端对应。范围 μ* 使用 `payload.parameters.extensions[i]` 的 `key=mu_star,value_kind=range,value_min/value_max`，不同时保留主标量。μ* 可留空且允许单端未知；其余参数及扩展证据不丢弃。非法文本不能通过客户端或服务端校验，错误定位到同一个编辑框，核对锚点仍采用规范数据路径。

## US6～US9 增量契约

参数和计算条件仍保存在原 payload 对象的 extensions，保留 field_key、未知字段、Evidence 和原数组位置。扩展输入非法数字不能变成合法空值。普通性质原始值和规范值契约不变。

热力学使用 payload.thermodynamic_stability={version:1,basis,cases}；各 case 的字段、枚举和温度约束见 Plan。当前 case 必须存在，缺省是 unknown、above_hull=null、ZPE unspecified；无示例数据默认。前后端拒绝无效版本、枚举、非有限/负数、错误单位、非 0 的 ΔE/ΔH 温度及跨模块伪装。value_kind=text、value_raw/value_text 为当前稳定性文本，服务端重新校验一致性。复制时仍生成新记录键。现有 payload_json 和完整导出无损携带全部 cases。

谱 GET /api/rag/spectra?target=...&target_id=... 返回 items/jobs/version/can_edit/can_review，摘要引用 collection.id/version、state_key、curve.id/kind、run.status、review；独立路由 /spectra/:collectionId，查询参数显式携带目标、状态、曲线、集合版本与站内返回地址。重新读取后不匹配即显示错误，不展示另一状态或旧版本。图像/导出使用相同目标参数与 api.download 鉴权；候选及质量只展示服务器已授权内容。

人工保存不改变 /api/rag/evidence/.../manual API：prepare 返回最新 endpoint/version，PUT 说明后串行 POST 文件，全部成功且草稿未再编辑才 complete。provide 需已有或待上传附件；none 需缺证原因并移除已存和待上传附件。busy、失败、历史与版本冲突维持 #138 规则。

## 模块默认折叠

初次挂载的四类模块均折叠；展开/收起仅改变原生 details 的 open 状态，不调用模块 onChange，不进入提交载荷。内容保留挂载，嵌套记录 Accordion 状态与未保存输入不因模块折叠丢失。模块身份继续由 module_key 决定；模块工具栏独立于折叠标题。

## 模块顺序兼容

模块上下移动入口已取消，不提供替代排序操作；仍使用原 property_modules 数组顺序和 display_order 保存合同，不强制重新排列历史数据。空模块删除仍有既有删除元数据及序号归一化，其他模块的相对顺序不变。US10 的默认折叠及草稿保留保持。

## US12/US13 材料状态契约

所有上传／返修及管理员科学草稿统一携带 state_kind 与 structure_optimization（缺省 unknown）。前者仅 theoretical/experimental/unknown；后者仅 unknown/classical_static/sscha，非 theoretical 必须 unknown。无 CIF 时也可记录论文明确给出的结构优化方法。完整材料导出和 Go 读取携带同名列。mixed 或非法值按字段定位拒绝，不映射。每状态最多一份非空直接结构或一个 confirmed/confirmed 候选；多份请求拒绝并提示不同优化几何分别建卡。原胞／惯用胞与格式表示放在该候选 representations，不创建额外 StructureModel。

## US14：DOS 展示例外

electronic_properties / property / dos_fermi 跳过单条记录折叠、定义选择和行下方证据摘要，直接使用通用核心行。文本镜像值只有名称、值类型、原始值、单位四项；非镜像文本与其他类型继续保留对应规范值编辑。definition_key/version、record_key、payload、evidence/evidences 及 API 合同不变；复制删除、定义错误和只读行为沿用共享表单。

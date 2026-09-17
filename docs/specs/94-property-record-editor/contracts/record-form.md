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

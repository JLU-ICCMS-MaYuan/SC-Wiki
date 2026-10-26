# CONTCAR/PDOS Tc 估算

## 功能说明

解析 VASP CONTCAR 和 PDOS 文件，提取氢子晶格、键长分布与费米能级附近态密度，并根据固定经验参数返回 Tc 估算值。

## 当前行为

- 使用 pymatgen 解析 CONTCAR。
- 统计氢原子、H-H 键长及键长分布。
- 读取 `PDOS_H.dat` 和最多四个金属 PDOS 值，计算态密度与耦合特征。
- 返回 Tc 估算及中间解释特征。
- 主站多模型页面以论文称呼 Tc assessment model 提供原输入流程，原 API 和公式保持不变。
- 缺少必要文件、文件无法解析、列数不足或关键数值为零时返回 400 错误。

## 工作流程

前端 `/tc-predict` 上传 CONTCAR 和 PDOS 文件；后端解析结构；识别氢和金属 PDOS；计算耦合、频率及 Tc；将数值和解释特征返回页面。

## 约束

- 必须包含可解析的 CONTCAR 和 `PDOS_H.dat`。
- 金属 PDOS 数量会补齐或截断为四个值。
- NumPy 被限制为 `<2.0`，以兼容 pymatgen。
- 已用真实原接口和合成 CONTCAR／PDOS 夹具完成主站端到端集成验证，不代表模型科学有效性。

## 代码与测试

- API：`backend/api/tc_predict.py`
- 页面：`frontend/src/pages/TcPredictPage.tsx`
- 依赖：`requirements.txt`
- 真实页面验证：`tests/06_ai_assisted_tc_estimation/local-prediction.cjs`

## 相关变更记录

[本地主站接入验收](../../specs/162-open-superconductor-model-comparison/local-integration-validation.md)；[论文命名核查](../../specs/162-open-superconductor-model-comparison/model-name-source.md)。

## 已知问题

- 经验公式的适用范围、校准数据和不确定度没有在当前实现中形成可验证的模型说明。

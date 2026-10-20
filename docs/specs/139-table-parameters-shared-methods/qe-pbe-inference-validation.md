# US5：QE的PBE推断验收

日期：2026-10-20；关联[#139](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/139)。用户已阅读完整增量草案并回复“继续”。

## 实现行为

READ只记录原子事实；关联阶段新增受限PBE推断，引用VASP软件、VASP-PBE和QE软件设置ID及同一材料/物相工作流依据。服务器验证来源、软件、阶段、范围、例外、已有值和候选冲突，只构造QE空泛函的PBE候选；强制paper_inference，不把VASP原子设置改为QE事实。

明确QE设置优先，已有人工值保护；缺少VASP-PBE、软件不符、范围不符、不同泛函及来源不完整时不补。结构阶段已有PBE扩展是推断依据，不是QE平坦字段已填写的证据。对候选目标，模型必须明确推断或给出排除理由，静默遗漏有一次纠正机会，仍缺失保留缺口。

来源关联保存inference_rule=vasp_pbe_to_qe_v1、来源设置ID、两端原文和“QE未直接报告”的解释。重读及来源核对维持uncertain/paper_inference，不自动升级为直接支持；值/来源变化沿既有版本机制失效。上下文缓存版本升级v6，旧生成缓存不沿用。复用现有补空与JSON来源合同，无数据库迁移，不通过此例外复制截断能、网格、展宽或电子理论。

## 自动化验证

- 新增test_qe_pbe_inference.py共25项，覆盖实际生成→应用→核对、JSON重读、自动补空标记、已有结构PBE扩展、QE明确设置优先、人工值、冲突、例外、错误/缺少来源、阶段与物相范围、源变化、静默遗漏纠正及明确排除。
- 独立HEAD归档仅叠加本次增量，7份相关测试共106项通过：本文件、test_calculation_method_semantics.py、test_issue139_scientific_context.py、test_issue139_workflow.py、test_issue139_table_parameters.py、test_property_evidence.py、test_evidence_proposals.py。
- Python编译与Git差异检查通过，仅保留现有spglib/SWIG/crypt弃用提示。
- 测试设置进程级DATABASE_URL=sqlite:///:memory:及测试JWT密钥，不使用生产库写入；模型和存储边界的固定响应只证明机械契约，不作为真实论文结论。

工作区同期存在另一项来源绑定功能修改，涉及相同文件。本次独立副本排除其association_review依赖，且对下述真实模型候选重新应用、重读与核对成功，证明本功能不依赖该并行改动。提交前将逐一核对[源码摘要](assets/qe-pbe-inference-verified-source.json)。

## 真实La–Sc–H验证

当前deepseek-v4-pro读取完整有效主文与SI提取文本，共2个窗口、159个来源块。只对格式有效、QE泛函为空的200 GPa记录副本进行关联验证。真实模型给出VASP/PBE与QE工作流联系，服务器生成并应用1条PBE推断，推断应用缺口为0。

写入JSON副本再读取后，值为PBE，basis_kind、source_kind均为paper_inference，核对状态保持uncertain。再将同一真实模型候选交给仅含本次增量的独立源码重放，同样应用1条、缺口0并保持推断身份。完整结果和哈希见[在线验证摘要](assets/qe-pbe-inference-live-validation.json)；原始全文、原始模型响应及失败尝试留在本地.data运行制品目录。

原任务的150 GPa字段已由用户填写PBE，本次没有覆盖；在线验证前后原任务草稿完全相等。没有写实际200 GPa记录、提交论文或授予人工批准，也没有重跑完整新PDF上传/MySQL提交链。

## 调查中保留的失败边界

- 首次模型只分配VASP扩展、遗漏QE判断：新增明确判断覆盖要求和有限纠正，防止静默遗漏。
- 167 GPa旧记录的单值类型残留范围字段，现有记录校验拒绝应用；该历史问题未在本次放宽或修复。改用本来就有效的200 GPa副本进行功能验收。
- 模型一度将已有结构PBE扩展误当作QE已填：明确平坦QE字段和结构扩展的区别并增加回归，随后真实验证成功。

以上尝试均保留制品，不把拒绝或未应用计作成功。真实关联阶段对AIMD等不适用于目标的普通设置仍有明确排除，不能把“PBE推断应用缺口0”说成所有论文条件无缺口。

## 需求覆盖与交付

FR-017/019、SC-009由两端来源、模型判断、候选构造及真实200 GPa例子覆盖；FR-018/020/022、SC-010由已有值、明确QE优先、不同候选及阶段反例覆盖；FR-021、SC-011由JSON重读、自动补空与核对身份保持、源变化和独立真实候选重放覆盖。

用户原话、继续确认、Spec/Plan/Research/契约、T037～T040与Overview同步。只提交本次增量，不推送，不批量改写历史草稿；新版远程文档链接待验证，Issue保持开放。

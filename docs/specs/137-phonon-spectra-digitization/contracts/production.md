# 正式谱接口与存储合同

已确认计划：[../production-plan.md](../production-plan.md)。模型目录 GPT-6-sol 用于本轮真实验收；运行使用任务模型，不更改全站默认配置。

## 数据身份与职责

- `spectrum_collections`：target/target_id、上传者、论文 revision、文件、材料状态/state_key、来源 JSON、当前 run、version 和逐曲线 review。图片为 FileStorage 引用，不公开物理路径。
- `spectrum_runs`：集合、input_hash、algorithm_version、model_name、状态、标定 JSON、服务器生成结果 JSON、失败原因与完成时间。input_hash 覆盖图片来源、标定、状态依赖及算法。成功运行不被后续标定覆盖。
- 原图数值、分辨率/归一化/联合候选分别保留。未知点为 null；不将整条谱塞入标量 PropertyRecord。
- 数值服务只接受标定，质量不能由客户端覆盖。状态条件或正文参考改变后判 stale，旧比较/采纳失效。提交/返修在原事务中绑定来源和材料；图片由私有 FileStorage 持久保存。

## HTTP 合同

公共前缀 `/api/rag/spectra`，Go 已有代理转发到 Python。

| 方法 | 路径 | 行为 |
| --- | --- | --- |
| GET | `?target=upload|paper|revision&target_id=...` | 当前谱列表、独立任务状态、目标 version、编辑/审核权限 |
| POST | `/extract` | target、target_id、expected_version；提交 RQ 独立自动提取 |
| PUT | `/{collection_id}/calibration` | 目标 version、集合 version 与完整 PanelCalibration；重提取并撤回旧采纳 |
| POST | `/{collection_id}/review` | 曲线 id、待核对/采纳/限定采纳/排除、有效 THz 区间与理由；仅审核者 |
| GET | `/{collection_id}/image` | 经相同目标权限检查读取私有原图 |
| GET | `/{collection_id}/export?format=json|csv` | 来源、版本、单位、质量与逐点原/候选值，公开限定采纳时掩膜同步裁剪 |
| GET | `/material-state/{paper_id}/{state_key}?expected_revision=...` | Go 完整材料状态导出使用；校验相同论文 revision |

修改均验证服务器目标及集合版本，冲突返回 409，不覆盖其他请求。异步队列失败、模型/来源不可用与标定错误独立呈现，不把论文成功改为失败。

## 标定

PanelCalibration 单一材料条件，包含 state_key、panel_id、图注、投影完整性/共尺度和 curves。曲线包含类型、元素投影、颜色、图框、频率轴方向、线性频率/幅值刻度、单位、图例排除、近零边界/参考带。服务器校验退化、不单调、非有限或越界坐标。单面板多条 α²F/累计 λ 须拆集合，不能随意配对。

频率 THz、cm-1、meV 转为 THz；绝对 DOS 密度同步雅可比。α²F/λ 定义或单位未证实时不提供物理积分。没有累计谱时不提供联合拟合；缺正文参考时没有百分比误差。

## 审核与公开

逐曲线审核状态 `needs_review`、`accepted`、`accepted_limited`、`excluded`。限定采纳要求有有限、递增且在原频域内的区间和非空理由。公开要求论文 `approved_revision=content_revision` 且该谱当前版本已采纳。旧版本、未分配、stale 或未采纳曲线不通过 JSON/CSV 或候选数组公开。限定采纳的质量指标说明完整运行指标与采纳频段的不同范围。

## 验证映射

FR-012→discovery/vision/engine→T014/T018；FR-013→models/服务/RQ/事务绑定→T015/T016；FR-014→SpectrumWorkspace/接口导出→T017；FR-015→engine 分项质量→T014/T017。SC-011 验证原 PDF 自动识图与独立合成 PDF，SC-012 验证隔离 MySQL、公开掩膜、并发及三个浏览器入口。


## production-v2 找图与重试兼容

标定颜色支持 red/blue/green/magenta/olive；olive 也是服务器和人工校对的正式颜色值。可选 IR 不存在时使用原 PDF，存储故障/摘要损坏仍报错。上下相接图片可按原 PDF 坐标渲染为完整图，source_mode=rendered_composite，保存 native_fragment_boxes_pdf_pt、固定 DPI 与变换；矢量图优先用图注和实际绘图框定位，不把纯文字页当作谱。

失败占位与有未解决问题的发现运行状态为 needs_review，不作为成功缓存；历史 succeeded 空结果读取时同样显示 needs_review。发现 detail 分别包含 collections、extracted_collections、curve_count。采纳规则和服务器质量计算保持不变，模型成功生成标定不代表数据已验收。


## 可选零证据的空值语义

zero_boundaries_thz 的空数组或 null 统一为 [null,null]，zero_reference_band_thz 的空数组或 null 统一为 null；均表示缺少证据，不表示零幅值、零频边界或允许插值。非空且长度错误仍拒绝。模型须分别屏蔽图内 λ 数值注记及同色文字，不能将文字当作累计曲线终点。

## T023 状态归属与摘要导航

模块入口按 state_key + collection_id + 曲线族归组：phonon_dos 的全部投影共用“查看声子 DOS”；alpha2f 与同集合 cumulative_lambda 共用“查看 α²F”。同状态不同集合／近似分别保留。无该族数值明确空态，不能拿其他状态或另一集合的累计 λ 配对。

详情 URL 保留 target、target_id、state_key、collection_version、run、return；curve 可选择实际存在的曲线。未归属以 state_key=unassigned 对应服务端 null，空结果集合可省略 curve，且只能查看真实来源及失败，不生成示例曲线。URL 中材料／集合／曲线／版本任一不匹配仍拒绝。权限由原接口决定，前端标签不能绕过。

详情从当前草稿或论文读取完整材料状态标签（包含相和压力）。手动确认归属只允许有 can_edit 权限、有有效标定且目标状态存在时走原 calibration PUT；保留已有曲线标定，复用任务和集合乐观版本检查。重新归属触发原异步数值及质量重算、旧采纳失效；前端返回对应状态显示排队／运行／失败，不能承诺请求受理即提取成功。保存出错和版本冲突不跳转、不覆盖当前选择。

## T025：性质模块内折叠

按用户最新要求，DOS 摘要与空态置于动力学模块折叠体，α²F／累计 λ 摘要与空态置于超导模块折叠体。已有标量模块和仅有谱的模块共用 PropertyModuleSection，默认收起，展开互不影响。折叠只改变界面可见性，不触发数据变更、谱下载、重新提取或归属修改；展开后的查看按钮仍使用既有详情身份和保存前置规则。

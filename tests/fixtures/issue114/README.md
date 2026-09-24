# #114 人工标注与离线评测

本目录定义人工评测格式，**当前未收集 50 篇人工标注论文**。合成样本只验证评分程序，
不是论文清单，不得用于宣布质量门通过。受限制论文、密钥、用户身份和本机绝对路径
不提交到仓库。契约与评分实现位于 `backend/ingest/pdf_benchmark.py`。

## 数据准备

每篇分配稳定 `paper_id`，登记主 PDF 及附件的 SHA-256；同一主 PDF 不重复计数。
正文与附件作为同一论文的来源集合，Evidence 指向实际来源的摘要。一篇可以有多个类别：

| 类别 | 含义 |
| --- | --- |
| `digital` | 正常数字 PDF |
| `scanned` | 扫描 PDF，复杂类别 |
| `double_column` | 双栏论文 |
| `multipage_table` | 多页表格，复杂类别 |
| `formula_dense` | 公式密集 |
| `figures_curves` | 图表和曲线 |
| `multi_pressure` | 多压力，复杂类别 |
| `multi_material` / `multi_method` | 多材料 / 多方法 |
| `supplementary` | 正文附补充材料 |
| `chinese` / `english` | 中文 / 英文 |

人工逐条核对材料、Tc、方法、压力与条件；不同压力、材料或方法的测量分别标注，
不能只保留最大 Tc。记录未采用行及理由，不能为了提高分数删除难例。`annotator`
使用人员代号，`reviewed_on` 保存核对日期。必须打开原文确认，不能把模型结果直接
标为人工事实。程序不能鉴定人工标注真实性，维护者仍须审核。

## 四份输入 JSON

未知字段、非有限数值、重复身份、非法区域均拒绝。评分不联网、不触发业务数据库写入。

### corpus.json：人工标注

顶层为 `schema_version: "1"`、`kind: "human" | "synthetic"`、`papers` 数组。
每篇包含 `paper_id`、`main_sha256`、`source_sha256s`、`categories`、`annotator`、
`reviewed_on` 和非空 `records`。使用实际文件的 64 位小写十六进制摘要。

记录示意（不是实际论文标注）：

```json
{
  "record_id": "tc-1",
  "fields": {"material": "LaH10", "tc_k": 200, "method": "resistivity"},
  "conditions": {"pressure_gpa": 150},
  "evidences": [{
    "file_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "pdf_page": 1,
    "bbox": [0.1, 0.1, 0.5, 0.2],
    "quote": "Tc = 200 K"
  }]
}
```

`fields` 保存科学记录身份和值，`conditions` 保存条件。实际评测必须预先统一字段
集合、缺失规则、单位、方法与条件枚举；至少比较材料、Tc（数值或上下限）、方法，
同时纳入实验/理论类别和已报告条件。两条链路使用相同契约，不能只为其中一条丢弃
困难字段。自由文本条件若需标准化，应预先固定映射并人工核对；评分不调用模型猜
同义词。当前是记录级精确评分，不宣称完成单个科学字段的语义准确率。

区域为左上原点 **0～1 归一化坐标**；IR 使用 PDF 点坐标，导出时分别除以该页宽、高。
PDF 页码从 1 起，不用印刷页码替代；标注不依赖解析器 block ID。

### legacy.json / new.json：成对运行结果

顶层为 `schema_version: "1"`、`run_id`、`pipeline_revision`、`parser_profile`、
`model`、`papers`。每篇包含 `paper_id`、`source_sha256s`、`status`、`records` 和
可选 `resources`。记录格式同标注，允许缺少 Evidence，但计入定位失败；来源集合
必须与标注一致。两次运行的源码版本、模型和方案分别保存，不合并运行身份。

`status` 为 `ready`、`failed`、`needs_review`、`cancelled` 或 `timeout`；非 ready
的 records 必须为空，部分 Claim 不当作已交付记录。未运行论文记为 `missing`，
全部漏召回，且阻止默认门；失败论文始终保留分母。

资源字段：`latency_seconds`、`input_tokens`、`output_tokens`、`cpu_seconds`、
`gpu_seconds`、`cost_usd`、`human_edits`。未实测时省略或 null，不能冒充 0。
报告保存逐论文资源、实测论文数和总量。当前需从固定的新旧上传结果导出这些输入；
也可使用下述运行驱动自动启动完整 RQ 上传并导出结果。

### checks.json：独立验收

```json
{
  "failure_recovery": {"passed": false, "evidence": "实际恢复测试记录的引用"},
  "legacy_revision_review": {"passed": false, "evidence": "实际兼容回归记录的引用"},
  "unsupported_writes": 0,
  "writes_audit_evidence": "提交事务与人工裁决审计记录的引用"
}
```

维护者依据真实验收填写；离线科学记录比较不能证明恢复、正式写库安全或 revision
兼容。只有真正通过才填 true，无依据正式写入计数来自提交审计，不从草稿引句推算。

## 执行

```bash
python -m backend.ingest.pdf_benchmark \
  --corpus "/path/to/corpus.json" \
  --legacy "/path/to/legacy.json" \
  --new "/path/to/new.json" \
  --checks "/path/to/checks.json" \
  --output "/path/to/report.json"
```

生成报告退出码为 0，即使质量未通过；用报告内 `quality_gate_passed` 判断。非法输入
返回非零，输出不能覆盖输入。四份输入与报告一起归档，报告记录规范 JSON 的摘要。

## 指标与门禁

- 正确记录要求 fields 与 conditions 均一致，采用一对一匹配；重复预测计假阳性。
  数字 200 与 200.0 相同，数字字符串不等同数字，化学式大小写不折叠，仅归一化空白。
- Precision、Recall、F1 用全部论文记录数做微平均；漏记录率为 1−Recall。
- 条件关联准确率为完整正确记录数 / 忽略条件后匹配的记录数，分母为 0 时记 0；
  必须结合 Recall 阅读，不能用条件准确率代替召回。
- 定位率分母为全部预测记录。成功要求科学记录正确、至少一条 Evidence，且提供的
  每条 Evidence 均对应标注的同文件、同页、规范引句完全相同、bbox 交并比≥0.5。
  使用最大二分匹配避免重复计数和输出顺序影响；空预测定位率为 0。
- 复杂总计只计每篇一次，各类别可交叉；扫描、多页表格、多压力必须分别提升，
  不能用汇总提升抵消某类退步。

默认门要求至少 50 篇不同主 PDF 的人工标注、全部类别有样本、新 F1 不下降、
定位率≥95%、无依据正式写入为 0、独立恢复/兼容验收通过。合成集不能通过。
只填汇总数字的旧报告不再接受，须重新生成版本 1 逐论文报告。此门不替代 Shadow、
真实供应商、人工标注真实性审查及整个 Feature 验收。

## 批量运行实际上传链路

`pdf_benchmark_runner` 通过本机服务的公开 API 创建任务、上传文件、轮询真实 Worker，
然后从同一服务的 artifact 目录读取 `result.json.ai_values` 和 IR。只生成草稿，不提交、
批准或发布论文；每完成一篇就原子保存结果，后续失败不抹掉已完成记录。没有运行的
论文仍会被评分器计为 missing。建议使用独立评测实例，并预留上传任务额度；导出后
不会自动删除任务或原始产物。若正式论文库已有相同文件，明确拒绝用重复任务结果评分。

准备 `sources.json`，将 corpus 中每个 paper_id 映射到本机文件及角色，例如：

```json
{
  "paper-001": [
    {"path": "/path/to/main.pdf", "role": "main"},
    {"path": "/path/to/supplement.pdf", "role": "supplementary"}
  ]
}
```

启动前逐个核对文件摘要与标注来源，正文必须唯一且匹配 main_sha256。中途换文件、
模型或源码会被拒绝。`SCWIKI_BENCHMARK_TOKEN` 是 **SC-Wiki 测试账号的登录令牌**，
不是 GitHub Token；只在本机配置环境变量，不写入标注、日志或报告。

```bash
python -m backend.ingest.pdf_benchmark_runner \
  --corpus "/path/to/corpus.json" --sources "/path/to/sources.json" \
  --base-url "http://127.0.0.1:8080" \
  --artifact-root "/path/to/sc-wiki-data/review_artifacts" \
  --profile legacy --output "/path/to/legacy.json"

python -m backend.ingest.pdf_benchmark_runner \
  --corpus "/path/to/corpus.json" --sources "/path/to/sources.json" \
  --base-url "http://127.0.0.1:8080" \
  --artifact-root "/path/to/sc-wiki-data/review_artifacts" \
  --profile layout --output "/path/to/new.json"
```

每篇默认等待 1800 秒；`--timeout` 可设置 0～7200 秒之间的正值。超时请求取消任务，
该篇作为 timeout 输出，不把部分候选计为成功记录。需要可用模型配置与在线 Worker；
此命令不会把没有凭据的测试替身当成真实模型。

自动导出的固定字段如下，人工标注必须独立遵循同一字段集合、保留未知字段的 null：

- fields：material、material_name、record_type、property_code、name_raw、value_kind、
  value_number、value_min、value_max、value_text、value_boolean、canonical_unit、
  method_code、method_raw、criterion_code、criterion_raw、uncertainty。
- conditions：pressure_value_gpa、pressure_min_gpa、pressure_max_gpa、temperature_value_k、
  magnetic_field_t、state_kind、reported_space_group_number，以及逐记录的 payload。
- evidences：仅从同一上传文件 IR 验证并归一化后的区域。旧链路缺少 IR 时不伪造区域。

上面的 tc_k/pressure_gpa 简例用于说明评分格式；使用自动导出时按本节字段名标注。
不能把模型导出值直接复制为标准答案，必须独立核对完整原文及所有应提取记录。

运行产物记录模型、供应商、实现文件 SHA-256 指纹、实际解析时延和 Worker 自身 CPU
时间；CPU 值不包含解析子进程、GPU 或远端模型资源。Token/GPU/费用没有实测时为空，
不是 0。完整人工标注与独立写入/恢复审计仍是默认切换的前置条件。

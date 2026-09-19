# 接口契约：科学数据编辑与结构补传

**GitHub Issue**：[#76](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/76)

**日期**：2026-09-01；2026-09-19 补充 [#110](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/110) 保存保留与回归验收。

**Spec**：[../spec.md](../spec.md)　**数据模型**：[../data-model.md](../data-model.md)

新增两个 Python 端点。既有 Go 接口不改动。

## C1：重写论文的科学数据

`PUT /api/rag/papers/{paper_id}/scientific-draft`

**权限**：`get_current_admin`——管理员与超级管理员。非管理员返回 403（FR-021）。

**请求体**：与上传草稿的 `material_states` 结构一致，复用同一形态使前后端可共享类型定义与校验。

```json
{
  "material_states": [
    {
      "material": "Sn",
      "material_family": { "id": 8, "name": "单质超导体", "status": "confirmed" },
      "structure_families": [],
      "element_count": 1,
      "material_dimensionality": "three_dimensional",
      "superconductor_kind": "conventional",
      "crystal_system": "unknown",
      "pressure_value_gpa": 0.001,
      "pressure_min_gpa": null,
      "pressure_max_gpa": null,
      "pressure_raw": null,
      "pressure_unit_raw": null,
      "reported_space_group_symbol": null,
      "reported_space_group_number": null,
      "state_kind": "experimental",
      "note": null,
      "calculation_context": null,
      "experimental_context": null,
      "tc_results": [
        { "result_kind": "experimental", "tc_method": "experimental", "tc_value_k": 3.78, "value_raw": "3.78", "unit_raw": "K", "is_representative": true }
      ],
      "properties": [
        { "name": "threshold current", "value_raw": "0.28", "unit": "A" }
      ]
    }
  ],
  "structure_candidates": [],
  "paper_type": "experimental"
}
```

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `material_states` | `array` | 是 | 完整替换该论文的材料状态图；空数组表示删除全部材料状态（综述论文合法） |
| `structure_candidates` | `array` | 否 | 已确认的结构候选，形态同上传草稿 |
| `paper_type` | `string` | 是 | 用于校验分支——非综述论文要求至少一个材料状态且每个状态有材料家族 |

**语义**：有实际变化时整体替换。服务端先快照既有结构和定义事件，再删除该论文当前科学实体并按请求体重建，最后恢复应保留的关联与审计链；全部处于同一事务（[../data-model.md](../data-model.md) 的删除顺序）。无变化请求直接返回 `unchanged: true`。

上方示例保留最初的 `tc_results` / `properties` 兼容形态；当前编辑器使用 `property_modules[].records[]`，并提交论文级 `superconductor_kind`、`material_families`。#110 的保留与回滚验收使用当前形态。

**为何是整体替换**：材料状态、Tc、物性、结构、上下文之间有多重外键与生成列约束，增量更新需为每种实体维护独立的匹配与差异计算逻辑；整体替换复用已验证的 `persist_scientific_draft`，语义简单且与提交链路产出一致（[../research.md](../research.md) R1）。

**成功响应**：

```json
{
  "ok": true,
  "data": {
    "paper_id": 9,
    "content_revision": 2,
    "review_status": "pending",
    "revision_bumped": true,
    "material_state_count": 3
  }
}
```

| 键 | 说明 |
| --- | --- |
| `content_revision` | 保存后的内容版本号 |
| `review_status` | 保存后的审核状态 |
| `revision_bumped` | 是否发生了升版；`true` 表示论文已从公开状态退回待审核 |
| `material_state_count` | 重建后的材料状态数量 |
| `unchanged` | 是否与当前科学数据相同；为 `true` 时不重建、不升版、不新增修改历史 |
| `structure_candidate_id_map` | 实际重建时返回候选身份到新 `structure_<id>` 的映射，用于同页连续保存 |
| `structure_key_map` | 实际重建时返回旧 `structure-<id>` 到新结构引用的映射；删除的结构映射为 `null` |

前端据 `revision_bumped` 决定提示文案：`true` 时告知管理员论文已退回待审核并暂不公开。

**状态相关行为**：

| 论文状态 | 行为 | `revision_bumped` |
| --- | --- | --- |
| `pending` | 原地重建，版本号不变（FR-012） | `false` |
| `approved` | 升版、清空已批准版本标记、状态改为 `pending`、迁移三张表版本号（FR-013–FR-016） | `true` |
| `rejected` | 拒绝，返回 409（[../research.md](../research.md) R10） | — |

**错误响应**：沿用 `_upload_error` 的 `{code, message}` 契约。

| 状态码 | code | 触发条件 |
| --- | --- | --- |
| 400 | `state_material_required` | 某材料状态缺少化学式；message 含「第 N 个材料状态」前缀以便前端定位 |
| 400 | `material_family_required` | 非综述论文的材料状态缺少材料家族 |
| 400 | `material_state_required` | 非综述论文的 `material_states` 为空 |
| 400 | `invalid_pressure_range` | 压强区间 min 大于 max |
| 403 | — | 非管理员（`get_current_admin` 抛出） |
| 404 | `paper_not_found` | 论文不存在 |
| 409 | `paper_status_not_editable` | 论文为 `rejected` 状态 |
| 409 | `structure_reference_stale` | 既有结构候选引用其他论文、旧结构身份或重复引用同一结构 |

**校验错误的定位契约**：错误 message 保留「第 N 个材料状态」前缀，与上传校对页共用同一定位机制（`frontend/src/components/UploadTaskEditor.tsx:148` 的正则）。Issue #75 会把该文案的后半句改为「缺少化学式」，前缀不变。

**事务性**：全部写入在单一事务内。任一步失败则论文的版本号、审核状态与科学数据完全保持保存前状态，且已批准论文仍然对外公开（FR-018、SC-006）。

**重复保存**：以当前详情或服务端返回的身份映射再次保存相同内容时，不重建、不升版、不重复写历史。`approved` 论文只有实际修改才升版并退回 `pending`。重放带旧结构 ID 的请求返回 409，前端应刷新或应用成功响应中的映射，不能沿用失效身份。结构删除参与无变化比较，不能因其余字段相同而漏保存。

## 保存保留与回归验收（#110）

- 既有 CIF/POSCAR 按真实格式传回；服务端将 POSCAR 转成校验用 CIF。预览生成的标准 CIF 仍可识别为同一未编辑结构，保存保留原格式、原文、计算方法、参数与来源。
- 管理员科学保存和上传者返修共用 `scientific_graph_preservation.py`。按候选身份映射结构、父子关系和物性引用；旧 `state.structure` 仅在同状态、同原文及可写字段一致时保留。新附件即使文本相同，也不能冒用旧结构的来源。
- 定义变更原事件完整归档到论文历史。`pending` 同版本且记录快照未变时，活动事件保留原 ID、前序事件关系并更新记录与结构引用；升版、记录编辑或删除后只保留历史，不恢复旧回滚资格。定义回滚额外比较完整当前快照，过期时返回 409 `definition_rollback_stale`。
- Go 元数据保存与 Python 科学保存共用操作 ID；第二段补齐原定义事件与最终版本。服务端检查论文、操作者、事件类型和版本，拒绝借用其他操作的审计记录。
- 前端成功后只同步结构身份，保留等待保存期间的后续输入、候选和删除选择。来源准备、权限和失败回滚规则保持有效。

2026-09-19 提交前验证：

| 验证范围 | 结果与证据 |
| --- | --- |
| Python 与真实存储 | `test_admin_scientific_preservation.py`、`test_paper_revisions.py`、`test_form_definitions.py`、`test_scientific_drafts.py`、`test_scientific_evidence.py` 共 69 项通过，无跳过；覆盖真实 HTTP/JWT、MySQL 事务、CIF/POSCAR、定义回滚、重排序、删除、旧身份、权限、无变化、升版及跨 Go 再审核 |
| 前端 | `admin-scientific-preservation.test.tsx` 与 `admin-edit-page.test.tsx` 共 14 项通过，覆盖快速审核转换、同页连续保存及等待期间输入保留 |
| Go 与构建 | `go test ./handlers -count=1` 及前端 `npm run build` 通过；显式连接隔离 MySQL 的 `TestCurrentMySQLQuickReview`、`TestCurrentMySQLPaperMetadata` 也通过，覆盖两种管理员角色 |

数据库为新建本地 MySQL 8 隔离库 `scwiki_commit_test`，仅绑定 `127.0.0.1:3318`。从空库按 #90 真实迁移脚本完成切换后，显式升级到 `20260918_0108`。仓库既有两个迁移头导致 `upgrade head` 无法选择；本次未修改该迁移分支，也不将定向升级表述为全迁移链通过。无变化用例已修正为读取已持久化的同一材料家族，避免将新增家族误当作无变化。

这些结果只证明本地修复与回归通过；没有回填业务数据、调用外部模型、推送或部署。

## C2：为论文补传结构附件

`POST /api/rag/papers/{paper_id}/structure-candidates`

**权限**：`get_current_admin`。非管理员返回 403（FR-021）。

**请求**：`multipart/form-data`

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `material_state_index` | `int` | 是 | 目标材料状态在 `material_states` 数组中的下标，`>= 0` |
| `file` | file | 是 | CIF 或 POSCAR 文件 |

**成功响应**：返回结构候选对象，形态与上传链路的同名端点一致，含校验结果与原胞/惯用胞两种表示。

```json
{
  "ok": true,
  "data": {
    "candidate_id": "cand_ab12cd34",
    "material_state_index": 0,
    "status": "valid",
    "structure_format": "cif",
    "validation": { "ase_valid": true, "atom_count": 4, "elements": ["Sn"] },
    "representations": {
      "conventional": { "cif": { "text": "data_Sn\n..." } },
      "primitive": { "cif": { "text": "data_Sn\n..." } }
    }
  }
}
```

**错误响应**：

| 状态码 | code | 触发条件 |
| --- | --- | --- |
| 400 | `invalid_structure_format` | 文件扩展名与内容都无法识别为 CIF 或 POSCAR |
| 400 | `structure_validation_failed` | 结构解析失败；message 含具体原因（FR-010） |
| 400 | `invalid_material_state_index` | 下标越界 |
| 403 | — | 非管理员 |
| 404 | `paper_not_found` | 论文不存在 |

**不直接落库**：该端点只产出并返回校验后的结构候选，不写入 `structure_models`。候选随后由 C1 的 `structure_candidates` 字段一并提交落库。理由是保持「先校验预览、确认后保存」的既有交互，与上传链路一致（[../research.md](../research.md) R6）。

**复用**：校验与表示生成复用 `backend/services/structure_candidates.py` 的 `build_structure_candidate`，与 `POST /api/rag/upload-tasks/{task_id}/structure-candidates`（`backend/api/rag.py:815`）同一实现。

## C3：既有接口不改动

| 接口 | 说明 |
| --- | --- |
| `PUT /api/admin/papers/:id` | 论文级字段保存，契约与 `paperUpdateFields` 白名单不变（本 Feature 范围外；Issue #74 会为双语列扩展该白名单） |
| `POST /api/admin/papers/:id/review` | 审核动作与分类批准工作流不变 |
| `GET /api/admin/papers/:id` | 响应契约不变，但**需补充预加载**（见下） |
| `POST /api/rag/papers/:id/publish` | 重新批准后的索引重建走既有链路（[../research.md](../research.md) R9） |

### `GET /api/admin/papers/:id` 需补充预加载

既有预加载（`goserver/handlers/admin.go:124-128`）只有四项：

```go
Preload("KeyProperties").
Preload("MaterialStates.Superconductor").
Preload("MaterialStates.MaterialFamily").
Preload("MaterialStates.StructureFamilyLinks.StructureFamily").
```

**缺失三项**：`MaterialStates.TcResults`、`MaterialStates.Properties`、`MaterialStates.Structures`。

后果：编辑页拿不到 Tc、材料状态级普通物性与结构附件——正是 FR-002、FR-003、FR-004 要求展示的内容。GORM 未预加载的关联会序列化为空数组（`json` tag 均带 `omitempty`），因此表现为「有材料状态但其下什么都没有」，且接口返回 200 无任何错误信号。

**改动性质**：只补 `Preload` 调用，不改响应形状定义——响应契约由模型的 `json` tag 决定，本就包含这些键。因此这是补齐数据加载而非契约变更。

**响应补充（2026-09-02，FR-024、SC-010）**：`material_states[].material_family` 与 `material_states[].structure_families[].structure_family` 增加返回 `name_en`（规范英文名）。此前 Go 模型对 `name_en` 是 `json:"-"`、`GET /api/papers/:id` 的 `materialStatesToDict` 只回 `name`，导致英文界面拿不到英文名、自建家族只能回退中文名。改动为：`MaterialFamily`/`StructureFamily` 模型的 `NameEN` 改为 `json:"name_en"`（管理端详情），`materialStatesToDict` 的 `family` 与结构家族 `gin.H` 补 `name_en`（公开详情）。`name` 键保持不变（仍为规范中文名），属向后兼容的增量。

```json
"material_family": { "id": 8, "name": "单质超导体", "name_en": "Elemental superconductor", "status": "confirmed" }
```

数据层配套：既有自建家族「单质超导体」（`name_zh = '单质超导体'`）的 `name_en` 由空串补齐为 `Elemental superconductor`（一次幂等数据迁移，见 [../data-model.md](../data-model.md) 家族英文名补齐）。

**注意 `KeyProperties` 与 `MaterialStates.Properties` 的区别**：前者是按 `(paper_id, paper_revision)` 挂在论文下的全部物性（扁平表，供既有物性编辑区使用），后者是按 `material_state_id` 挂在材料状态下的同一批记录。编辑页的材料状态卡片需要后者以便按材料状态分组展示。两者指向同一张 `superconductor_properties` 表，不是重复数据。

## C4：前端调用编排

保存操作分两次请求，顺序与失败处理：

```text
1. PUT /api/admin/papers/:id           （论文级字段，Go）
   失败 → 提示论文级保存失败，终止；不调用第 2 步
   成功 → 继续

2. PUT /api/rag/papers/:id/scientific-draft   （科学数据，Python）
   失败 → 提示「论文信息已保存，但超导性质保存失败：<原因>」，
          明确告知管理员只需重试科学数据部分（FR-019）
   成功 → 若 revision_bumped 为 true，提示论文已退回待审核并暂不公开
```

**为何先论文级后科学数据**：论文级保存是低风险操作（单表字段更新），科学数据是高风险操作（多表删除重建）。先做低风险的，使「部分成功」落在更容易理解和恢复的状态上。

**不引入分布式事务**：两次请求分属不同服务与不同事务（[../research.md](../research.md) R2）。前端承担编排与失败提示职责。

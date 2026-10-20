# 接口契约：结构候选、预览与导出

**GitHub Issue**：[#49](https://github.com/JLU-ICCMS-MaYuan/SC-Wiki/issues/49)

## 2026-10-20 论文结构资料接口

- `POST /api/rag/structural-records/search`：公开的无 Tc 资料查询。请求包含 `elements`／`formula`、既有 `mode` 语义、关键词、压力与年份范围及独立的 `limit`／`offset`。只返回当前已批准版本中明确保留的模型或晶格观测；不要求 Tc，不查询提取问题。结构结果和 Tc 结果分别说明适用筛选。
- `GET /api/rag/structural-records/paper/{paper_id}`：按论文权限列出当前资料；有编辑权限者可核对 pending／excluded，公开读者只看 retained。
- `GET /api/rag/structural-records/{id}`：同时校验论文可见性、当前资料 revision 和保留状态；无权限或旧版本统一不可访问。
- `GET /api/rag/structural-records/{id}/download?format=json|csv|cif|poscar&cell=primitive|conventional`：带来源导出。晶格观测／问题请求原子结构格式返回 400；无权限或非当前版本返回 404。
- `POST /api/rag/structural-records/reextract`：上传／返修所有者从原附件重新读取的只读预览。请求 `target=upload|revision,target_id`，核验文件哈希、有效角色和草稿状态，返回模型、观测、问题、解析版本及 `model_calls=0`。不写草稿、记录或论文；界面明确“应用预览到表单”后，仍须保存主表单。编辑版本在等待期间变化则拒绝应用，已确认／人工决定及结构附件受保护。

资料表未迁移时，读取／正式写入返回带 `structural_migration_required` 说明的 503，不把不可用显示为“没有数据”。预览不依赖新增表就绪。来源来自原附件，不默认重新调用 LLM；布局不支持或缺字段时保留具体问题，不以猜测值生成成功记录。

## 草稿响应扩展

`GET /api/upload-tasks/{task_id}` 和现有任务详情响应在当前 `state_schema_version` 下增加：

```json
{
  "structure_candidates": [
    {
      "candidate_id": "sc-01",
      "material_state_ref": "ms-01",
      "source_kind": "pdf_derived",
      "status": "valid",
      "confirmation": "unreviewed",
      "validation": {"atom_count": 14, "elements": ["La", "H"], "ase_valid": true},
      "derivation": {"kind": "space_group_expansion", "label": "推导"},
      "sources": [{"file_id": "file-1", "page": 4, "table": "Table 2", "quote": "..."}],
      "representations": {
        "primitive": {"cif": {"available": true}, "poscar": {"available": true}},
        "conventional": {"cif": {"available": true}, "poscar": {"available": true}}
      }
    }
  ]
}
```

响应不得包含服务器绝对路径、Redis key、RQ job id、LLM 原始响应或无权限候选。

## 草稿更新

`PUT /api/upload-tasks/{task_id}/draft` 接受候选确认、排除、人工修正和导出偏好。服务端必须
重新验证用户提交的结构文本，不信任客户端的 `validation`、`hash` 或 `status`。

```json
{
  "structure_candidates": [
    {
      "candidate_id": "sc-01",
      "confirmation": "confirmed",
      "user_note": "核对 Table 2，保留该压力相"
    }
  ]
}
```

## 预览与导出

- `GET /api/papers/{paper_id}/structures/{structure_id}/preview?cell=conventional`：只返回已授权
  论文当前 revision 的惯用胞预览数据，默认 `cell=conventional`。
- `GET /api/papers/{paper_id}/structures/{structure_id}/download?cell=primitive|conventional&format=cif|poscar`：
  返回对应派生文件流，并在响应中声明 `Content-Disposition` 和结构表示标签。

导出前必须执行论文权限、revision 一致性和结构存在性检查。非法 `cell` 或 `format` 返回 400；
无权限或未批准 revision 返回统一 404/403 语义，具体状态沿用现有论文 API 契约，不泄露候选存在性。

## 提交约束

状态规范几何只接收 `confirmation=confirmed` 且 `validation.ase_valid=true` 的候选；服务端重新
构造和校验派生结构，在同一事务中创建 `StructureModel`、`PaperEvidence` 和
`StructureModelEvidence`。任何失败整体回滚。

独立论文资料由 `retention` 决定内部保留／公开资格，与规范几何确认相互独立；pending／excluded 可随科学草稿保存但不公开。完整模型服务端重新读取并校验化学计量；部分观测重新校验数值、单位和来源，派生参数不信任客户端值。公开 JSON 使用科学字段白名单，不包含人工备注及内部附加元数据。

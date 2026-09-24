"""把领域提取候选独立转换为 Claim，并用上传 IR 重新定位，不信任模型的 validated。"""
from __future__ import annotations

from .claim_evidence import Claim, EvidenceLocator, validate_claim
from .document_ir import DocumentIR, content_hash


RECORD_LISTS = {"tc_results", "properties", "records"}


def _locators(raw_evidences, documents, default_file=None):
    located = []
    for evidence in raw_evidences:
        if not isinstance(evidence, dict):
            return []
        file_id = evidence.get("file_id") or default_file
        quote = str(evidence.get("quote") or "")
        requested_page = evidence.get("pdf_page", evidence.get("page", evidence.get("page_start")))
        candidates = []
        for ir in documents.values():
            if file_id is not None and str(file_id) != ir.source_file_id:
                continue
            for block in ir.blocks:
                if requested_page is not None and str(block.pdf_page) != str(requested_page):
                    continue
                if evidence.get("block_id") and evidence["block_id"] != block.block_id:
                    continue
                if quote.strip() and " ".join(quote.split()) in " ".join(block.text.split()):
                    candidates.append((ir, block))
        # 同一表的父块与唯一单元格重复包含原句时，保留更细的来源。
        parent_ids = {b.parent_block_id for _, b in candidates if b.parent_block_id}
        candidates = [(ir, b) for ir, b in candidates if b.block_id not in parent_ids]
        if len(candidates) != 1:
            return []
        ir, block = candidates[0]
        # 模型未返回几何时可从 IR 回填；返回了错误的定位不能被自动修正。
        kind = block.metadata.get("source_kind") or {"text":"text_layer", "ocr":"ocr", "vlm":"vision"}[ir.parser["mode"]]
        raw = dict(file_id=ir.source_file_id, source_version=ir.source_version, pdf_page=block.pdf_page,
            block_id=block.block_id, quote=quote, parser=ir.parser["name"], parser_version=ir.parser["version"], source_kind=kind)
        for key in ("source_version","parser","parser_version","source_kind","bbox","polygon","printed_page","table_id","figure_id"):
            if key in evidence:
                raw[key] = evidence[key]
        try:
            located.append(EvidenceLocator.model_validate(raw))
        except ValueError:
            return []
    return located


def claims_from_candidates(candidate: dict, documents: dict[str, DocumentIR], *, prefix="", legacy_sources: dict[str, str] | None = None) -> list[Claim]:
    claims = []
    default_file = (candidate.get("_source") or {}).get("file_id")

    def add(path, value, node, inherited):
        raw_evidence = list(node.get("evidences") or [])
        if isinstance(node.get("evidence"), dict):
            raw_evidence.append(node["evidence"])
        if not raw_evidence:
            raw_evidence = inherited
        if legacy_sources and raw_evidence and all(
            str(e.get("file_id") or default_file) in legacy_sources and e.get("quote")
            and " ".join(e["quote"].split()) in " ".join(legacy_sources[str(e.get("file_id") or default_file)].split())
            for e in raw_evidence if isinstance(e, dict)
        ) and all(isinstance(e, dict) for e in raw_evidence):
            return  # 非 PDF 来源继续经过共享来源核对，不伪造 PDF 页码和块。
        evidences = _locators(raw_evidence, documents, default_file)
        kind = evidences[0].source_kind if evidences else "text_layer"
        basis = node.get("basis_kind", "paper_quote")
        if basis not in {"paper_quote","paper_inference","general_knowledge"}:
            basis = "general_knowledge"
        identity = content_hash(default_file, path, node.get("record_key"), value, [e.model_dump(mode="json") for e in evidences])
        claim = Claim(claim_id=identity, target_path=path, value=value, raw_value=value,
                      basis_kind=basis, source_kind=kind, evidences=evidences)
        claims.append(validate_claim(claim, documents).claim)

    def walk(node, path, inherited, record=False):
        if not isinstance(node, dict):
            return
        if node.get("scope") == "referenced_work":
            return
        own = [node["evidence"]] if isinstance(node.get("evidence"),dict) else list(node.get("evidences") or inherited)
        if record:
            value = {k:v for k,v in node.items() if k not in {"evidence","evidences","scope","basis_kind"}}
            add(path, value, node, own)
            return
        # 材料状态条件也必须有来源，不能只核对 Tc 数字。
        if "material_states[" in path and not any(key in path for key in ("property_modules[","tc_results[","properties[")):
            values = {key:node[key] for key in ("material","material_name","pressure_value_gpa","pressure_min_gpa",
                "pressure_max_gpa","pressure_raw","pressure_unit_raw","state_kind","temperature_value_k",
                "magnetic_field_t","magnetic_field_value_t","temperature_raw","temperature_unit_raw","note",
                "reported_space_group_number","reported_space_group_symbol",
                "material_dimensionality","material_family","structure_families")
                if node.get(key) is not None and node.get(key) != ""}
            if values:
                add(path, values, node, own)
        for key,value in node.items():
            if key in {"evidence","evidences","_source"}:
                continue
            if isinstance(value, list) and key in RECORD_LISTS | {"material_states","property_modules"}:
                for index,item in enumerate(value):
                    walk(item, f"{path}.{key}[{index}]".lstrip("."), own, key in RECORD_LISTS)
    walk(candidate, prefix, [])
    return claims


def carry_state_evidence(draft: dict, claims: list[Claim]) -> None:
    """只对科学值完全匹配的状态继承已验证出处，避免汇总丢掉来源。"""
    for state in draft.get("material_states", []):
        if state.get("evidence") or state.get("evidences"):
            continue
        matches = [c for c in claims if c.status == "validated" and isinstance(c.value, dict)
                   and c.value.get("material") and all(state.get(k) == v for k, v in c.value.items())]
        if len(matches) == 1:
            state["evidences"] = [e.model_dump(mode="json") | {"page": e.pdf_page} for e in matches[0].evidences]


def apply_claim_evidence(root: dict, claims: list[Claim]) -> None:
    """只回填服务端生成路径上的已验证出处，科学值保持不变。"""
    import re
    for claim in claims:
        if claim.status != "validated":
            continue
        node = root
        try:
            for name, index in re.findall(r"([a-z_]+)|\[(\d+)\]", claim.target_path):
                node = node[name] if name else node[int(index)]
        except (KeyError, IndexError, TypeError):
            continue
        if isinstance(node, dict):
            node.pop("evidence", None)
            node["evidences"] = [e.model_dump(mode="json") | {"page":e.pdf_page} for e in claim.evidences]


def missing_tc_measurements(before: list[Claim], after: list[Claim]) -> list[str]:
    """防止汇总丢掉同一段落中的不同 Tc、压力或方法；未知条件允许后续补全。"""
    from decimal import Decimal, InvalidOperation
    from .property_modules import THEORETICAL_METHODS, EXPERIMENTAL_METHODS
    known_methods = THEORETICAL_METHODS | EXPERIMENTAL_METHODS
    def number(value):
        if value is None or isinstance(value, bool):
            return None
        try:
            return str(Decimal(str(value)).normalize())
        except InvalidOperation:
            return None
    def measurements(claims):
        states = {c.target_path:c.value for c in claims if isinstance(c.value, dict) and c.value.get("material")}
        items = []
        for claim in claims:
            value=claim.value
            if not isinstance(value, dict):
                continue
            legacy=any(k in value for k in ("tc_value_k","tc_min_k","tc_max_k"))
            if not legacy and value.get("property_code")!="tc":
                continue
            scalar=number(value.get("tc_value_k" if legacy else "value_number"))
            low=scalar or number(value.get("tc_min_k" if legacy else "value_min"))
            high=scalar or number(value.get("tc_max_k" if legacy else "value_max"))
            if low is None and high is None:
                continue
            item={"low":low,"high":high}
            parents=[path for path in states if claim.target_path.startswith(path+".")]
            if parents:
                parent=states[max(parents,key=len)]
                item["material"]=str(parent["material"]).strip().casefold()
                for key in ("pressure_value_gpa","pressure_min_gpa","pressure_max_gpa","reported_space_group_number"):
                    normalized=number(parent.get(key))
                    if normalized is not None: item[key]=normalized
            method=value.get("tc_method" if legacy else "method_code")
            if method in known_methods-{"unknown"}: item["method"]=method
            # experimental 表示结果类别，不能当作 resistivity 方法证据。
            kind=value.get("result_kind" if legacy else "record_type")
            if kind in {"experimental","theoretical","measured_tc","predicted_tc"}:
                item["kind"]={"experimental":"measured_tc","theoretical":"predicted_tc"}.get(kind,kind)
            items.append((claim.claim_id,item))
        return items
    actual=[item for _,item in measurements(after)]
    return [key for key,expected in measurements(before)
            if not any(all(found.get(k)==v for k,v in expected.items()) for found in actual)]

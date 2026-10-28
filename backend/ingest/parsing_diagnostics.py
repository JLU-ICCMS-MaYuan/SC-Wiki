"""解析差异的只读分流：不改原文、科学值或人工审核结论。"""
from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
import hashlib
import difflib
import json
import re
import unicodedata

VERSION = "parsing-triage-v1"
_GREEK = {"alpha": "α", "beta": "β", "gamma": "γ", "mu": "μ", "omega": "ω",
          "lambda": "λ", "Delta": "Δ", "times": "×", "cdot": "·", "circ": "°"}
_SUB = str.maketrans("₀₁₂₃₄₅₆₇₈₉", "0123456789")
_SUPER = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻", "0123456789+-")


def notation_key(text: str) -> str:
    """只展开明确的文字/公式表示；不删除负号、电荷、上标、横线或数值。"""
    value = unicodedata.normalize("NFC", text or "")
    value = re.sub(r"[₀₁₂₃₄₅₆₇₈₉]+", lambda m: "_{" + m[0].translate(_SUB) + "}", value)
    value = re.sub(r"[⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻]+", lambda m: "^{" + m[0].translate(_SUPER) + "}", value)
    for name, replacement in _GREEK.items():
        value = re.sub(r"\\" + name + r"\b", lambda _: replacement, value)
    value = value.translate(str.maketrans({"−": "-", "–": "-", "—": "-", "∆": "Δ", "“": '"', "”": '"'}))
    value = re.sub(r"\\[,;:!]", " ", value)
    for _ in range(12):
        before = value
        value = re.sub(r"_\s*\{\s*([0-9]+)\s*\}", r"_\1", value)
        value = re.sub(r"\\(?:mathrm|mathbf|mathsf)\s*\{([^{}]*)\}", lambda m: re.sub(r"\s", "", m[1]), value)
        value = re.sub(r"\\text\s*\{([^{}]*)\}", r"\1", value)
        value = re.sub(r"\\mathring\s*\{\s*A\s*\}", "Å", value)
        if before == value:
            break
    value = re.sub(r"\s*([_^])\s*", r"\1", value)
    value = re.sub(r"\^\s*\{([^{}]*)\}", lambda m: "^{" + re.sub(r"\s", "", m[1]) + "}", value)
    value = re.sub(r"\^([*0-9])(?=[^0-9{}]|$)", r"^{\1}", value)
    value = value.replace("μ^{*}", "μ*").replace("[˚]", "[°]").replace("[^{°}]", "[°]")
    # 仅明确化学式的数字下标可用纯文本书写；一般数学变量下标不抹除。
    value = re.sub(r"(?<![A-Za-z0-9_])(?:[A-Z][a-z]?(?:_?\d+)?)+(?![A-Za-z0-9_])",
                   lambda m: m[0].replace("_", ""), value)
    value = re.sub(r"\s*([,;()\[\]])\s*", r"\1", value)
    value = re.sub(r"\s*([+=/])\s*", r"\1", value)
    value = " ".join(value.split())
    return value[:-1].rstrip() if value.endswith('.') and not value.endswith('..') else value


def _hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()


def _notation_candidate(text):
    """只用于分组，不授予等价结论；空格/下标表示仍须原文核查。"""
    value = re.sub(r"\\(?:mathrm|mathbf|mathsf|text)\b", "", notation_key(text))
    return re.sub(r"[\s{}_]", "", value)


def _grid(table, blocks):
    if table is None or not table.cells or table.row_count < 1 or table.column_count < 1:
        return None
    cells, positions = [], set()
    for cell in table.cells:
        position = (cell.row_index, cell.column_index)
        metadata = blocks[cell.block_id].metadata if cell.block_id in blocks else {}
        spans = [metadata.get(key, 1) for key in ("row_span", "column_span")]
        if (position in positions or any(type(value) is not int or value < 1 for value in spans)
                or not 0 <= cell.row_index < table.row_count
                or not 0 <= cell.column_index < table.column_count
                or cell.row_index + spans[0] > table.row_count
                or cell.column_index + spans[1] > table.column_count):
            return None
        positions.add(position)
        cells.append((*position, notation_key(cell.text), *spans))
    return (table.row_count, table.column_count, sorted(cells))


def _impact_index(draft):
    result = defaultdict(list)
    def add(node, descriptor):
        evidences = [*(node.get("evidences") or []), *([node["evidence"]] if isinstance(node.get("evidence"), dict) else [])]
        for evidence in evidences:
            if isinstance(evidence, dict) and evidence.get("file_id") and evidence.get("block_id"):
                key = (str(evidence["file_id"]), str(evidence["block_id"]))
                if descriptor not in result[key]:
                    result[key].append(descriptor)
    for state in draft.get("material_states") or []:
        name = str(state.get("material") or state.get("material_name") or "")
        label = name + (f" · {state['pressure_value_gpa']} GPa" if state.get("pressure_value_gpa") is not None else "")
        add(state, {"state_key": state.get("state_key"), "label": label, "kind": "state"})
        for module in state.get("property_modules") or []:
            for record in module.get("records") or []:
                add(record, {"state_key": state.get("state_key"), "record_key": record.get("record_key"),
                    "module_key": module.get("module_key"), "kind": "record",
                    "label": label + " · " + str(record.get("name_raw") or record.get("property_code") or "")})
    return result


def read_pdf_regions(documents, paths):
    """原PDF只读检查，绑定上传摘要；不把文字层一致冒充视觉/科学审核。"""
    import pymupdf
    results = {}
    for fid, path in paths.items():
        ir = documents.get(fid)
        if ir is None:
            continue
        try:
            if hashlib.sha256(path.read_bytes()).hexdigest() != ir.source_sha256:
                for page in ir.pages:
                    results[(fid, page.pdf_page)] = {"error": "source_changed"}
                continue
            with pymupdf.open(path) as pdf:
                for page in pdf:
                    lines = []
                    for block in page.get_text("dict")["blocks"]:
                        for line in block.get("lines", []):
                            lines.append({"text": "".join(s["text"] for s in line["spans"]), "bbox": line["bbox"]})
                    results[(fid, page.number + 1)] = {"lines": lines, "page_text": page.get_text()}
        except (OSError, ValueError, RuntimeError):
            for page in ir.pages:
                results[(fid, page.pdf_page)] = {"error": "original_unavailable"}
            continue
    return results


def _native_excerpt(region, page):
    if not region or not page:
        return ""
    from .complementary_ir import overlap
    return "\n".join(line["text"] for line in page.get("lines", []) if overlap(region, line["bbox"]) >= .6)


def _difference_excerpt(selected, alternatives):
    changes = []
    for alternative in alternatives:
        a, b = notation_key(selected), notation_key(alternative.get("text", ""))
        for tag, a0, a1, b0, b1 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
            if tag != "equal":
                left, right = a[max(0, a0-14):min(len(a), a1+14)], b[max(0, b0-14):min(len(b), b1+14)]
                entry = {"selected": left[:180] + ('…' if len(left) > 180 else ''),
                         "alternative": right[:180] + ('…' if len(right) > 180 else '')}
                if entry not in changes:
                    changes.append(entry)
    return changes[:5], len(changes)


def _category(item, ir, native):
    text = str(item.get("selected_text") or "")
    alternatives = item.get("alternatives") or []
    blocks = {b.block_id: b for b in ir.blocks} if ir else {}
    block = blocks.get(item.get("selected"))
    bbox = block.bbox if block else None
    page = next((p for p in ir.pages if p.pdf_page == item.get("pdf_page")), None) if ir else None
    evidence = {"native_text": _native_excerpt(bbox, native), "source_sha256": ir.source_sha256 if ir else None}
    if bbox and page:
        footer = bbox[1] >= page.height * .88 and (text.strip() == str(item["pdf_page"])
            or re.fullmatch(r"\d+\s+of\s+\d+.*|[A-Z][\w .-]{0,35} et al\.|[\w ]{1,35}Early Edition", text.strip()))
        margin = bbox[2] <= page.width * .05 and bool(re.search(r"downloaded|printed", evidence["native_text"], re.I))
        if footer or margin:
            return "layout", "system_checked", "layout_verified", evidence
    by_engine = defaultdict(list)
    for alt in alternatives:
        by_engine[alt.get("engine")].append(alt)
    if alternatives and all(len(group) > 1 and " ".join(text.split()) == " ".join(" ".join(
            a["text"] for a in sorted(group, key=lambda a: ((a.get("bbox") or [0,0])[1], (a.get("bbox") or [0])[0]))).split())
            for group in by_engine.values()):
        return "segmentation", "system_checked", "segments_equal", evidence
    if item.get("kind") == "table":
        tables = {t.block_id: t for t in ir.tables} if ir else {}
        grid = _grid(tables.get(item.get("selected")), blocks)
        same = bool(grid and alternatives and all(_grid(tables.get(a.get("block_id")), blocks) == grid for a in alternatives))
        return "table", "system_checked" if same else "system_pending", "table_grid_equal" if same else "table_needs_alignment", evidence
    key = notation_key(text)
    if key and alternatives and all(notation_key(a.get("text", "")) == key for a in alternatives):
        return "notation", "system_checked", "notation_equal", evidence
    if key and alternatives and all(_notation_candidate(a.get("text", "")) == _notation_candidate(text) for a in alternatives):
        return "notation", "system_pending", "notation_candidate", evidence
    def identifiers(value):
        return re.findall(r"\b[ctomh][A-Za-z]\d+\b|\b(?:[A-Z][a-z]?\d*){2,}\b", notation_key(value))
    def symbols(value):
        return re.findall(r"\*|\^\{[^}]+\}|\\(?:bar|overline|underline|hat|widetilde)\b|[\u0300-\u036f]|Å|\b(?:meV|eV|Ry|GPa|cm)\b",
                          notation_key(value))
    symbol_changed = any(symbols(a.get("text", "")) != symbols(text) for a in alternatives)
    category = "identifier" if not symbol_changed and any(identifiers(a.get("text", "")) != identifiers(text) for a in alternatives) else "symbol"
    raw = evidence["native_text"]
    if raw and not re.search(r"[ðÞ¼�]", raw):
        native_key = notation_key(raw)
        if native_key == key:
            evidence["text_layer_match"] = "selected"
        elif any(notation_key(a.get("text", "")) == native_key for a in alternatives):
            evidence["text_layer_match"] = "alternative"
    return category, "system_pending", "original_check_needed", evidence


def annotate_differences(draft, documents, files, *, pdf_regions=None):
    """返回带诊断的副本；原值和原始候选不修改，未知关联继续标为待追踪。"""
    result = deepcopy(draft)
    filenames = {f["file_id"]: f for f in files}
    impacts = _impact_index(draft)
    rows = []
    for raw in draft.get("parsing_conflicts") or []:
        item = deepcopy(raw)
        identity = {k: item.get(k) for k in ("file_id", "anchor", "selected", "pdf_page")}
        signature = _hash({"rule": VERSION, "identity": identity, "text": item.get("selected_text"),
                           "alternatives": [(a.get("block_id"), a.get("engine"), a.get("text")) for a in item.get("alternatives") or []]})
        category, status, reason, evidence = _category(item, documents.get(item["file_id"]), (pdf_regions or {}).get((item["file_id"], item["pdf_page"])))
        original_error = (pdf_regions or {}).get((item["file_id"], item["pdf_page"]), {}).get("error")
        if original_error:
            evidence["source_error"] = original_error
            status, reason = "system_pending", "original_unavailable"
        raw_native = evidence.pop("native_text")
        evidence.update(native_text_excerpt=raw_native[:400], native_text_sha256=_hash(raw_native))
        differences, difference_count = _difference_excerpt(item.get("selected_text") or "", item.get("alternatives") or []) if category != "segmentation" else ([], 0)
        linked = impacts.get((item["file_id"], item.get("selected")), [])
        file = filenames.get(item["file_id"], {})
        item["triage"] = {"id": _hash(identity), "version": signature, "rule_version": VERSION,
            "category": category, "status": status, "reason": reason,
            "filename": file.get("original_filename"), "file_role": file.get("role"), "evidence": evidence,
            "differences": differences, "difference_count": difference_count,
            "impact": {"status": "referenced" if linked else "unmapped", "references": linked,
                       "scope": "parse_snapshot", "unmapped_domains": ["spectra", "page_or_quote_only_links"]}}
        rows.append(item)
    result["parsing_conflicts"] = rows
    for item in result.get("bibliography_conflicts") or []:
        field = item.get("field")
        source = ((result.get("bibliography_sources") or {}).get("fields") or {}).get(field, {})
        verified = source.get("publication_verification") or {}
        a, b = item.get("grobid_value"), item.get("extracted_value")
        status, reason = "system_pending", "bibliography_check_needed"
        if field == "authors" and isinstance(a, list) and isinstance(b, list) and len(a) == len(b) and all(
                re.sub(r"[.\s]", "", str(x)) == re.sub(r"[.\s]", "", str(y)) for x, y in zip(a, b)):
            status, reason = "system_checked", "author_punctuation"
        if field == "abstract" and source.get("selection_rule") == "layout-keyword-boundary-v1" and source.get("selected_text") == result.get("paper", {}).get("abstract"):
            status, reason = "system_checked", "abstract_boundary"
        if field == "year" and verified.get("status") == "verified" and result.get("paper", {}).get("year") == verified.get("year"):
            status, reason = "system_checked", "publication_verified"
        elif field == "year" and verified.get("status") == "ambiguous":
            status, reason = "user_review", "publication_year_choice"
        item["triage"] = {"id": _hash(["bibliography", field, a, b]), "category": "bibliography",
            "status": status, "reason": reason, "field": field,
            "checked_value": result.get("paper", {}).get(field), "evidence": verified}
    return result

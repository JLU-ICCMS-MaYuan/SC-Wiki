"""验证真实数据边界：文件身份、互补来源、表格、引用和报告转义。"""
import json
from pathlib import Path

import pymupdf
import pytest

from backend.ingest.document_ir import DocumentIR
from backend.ingest.document_parsers import DocumentSource, ParseOptions
from backend.ingest.structured_pdf import IrBuilder
from backend.ingest.document_ir import PageGeometry
from scripts.complementary_pdf_demo.complement import complement
from scripts.complementary_pdf_demo.parsers import convert_marker
from scripts.complementary_pdf_demo.run import validate_case, parse_one
from scripts.complementary_pdf_demo.report import fields_for


def document(engine, file_id="main", page=1, text="Tc = 200 K", bbox=(10, 10, 100, 40), kind="paragraph"):
    source = DocumentSource(Path("unused.pdf"), file_id, sha256="a" * 64)
    builder = IrBuilder(source, ParseOptions(profile="demo"), engine, "1", [PageGeometry(pdf_page=1, width=200, height=300),
                        PageGeometry(pdf_page=2, width=200, height=300)], "text")
    block = builder.add(page, kind, text, bbox, metadata={"engine": engine})
    return builder.finish(), block


def test_complement_preserves_conflicting_numbers_and_original_ids():
    a, ab = document("docling", text="Tc = 200 K")
    b, bb = document("mineru", text="Tc = 999 K")
    c, cb = document("marker", text="Tc = 200 K")
    original = b.model_dump(mode="json")
    result, groups = complement({"docling": a, "mineru": b, "marker": c})
    assert {ab.block_id, bb.block_id, cb.block_id} <= {x.block_id for x in result.blocks}
    assert result.block(bb.block_id).text == "Tc = 999 K"
    assert groups[0]["has_text_difference"]
    assert groups[0]["semantic_resolution"] == "unreviewed"
    assert b.model_dump(mode="json") == original


def test_complement_never_crosses_files_or_pages():
    a, _ = document("docling", page=1)
    b, _ = document("mineru", page=2)
    c, _ = document("marker", page=1)
    result, groups = complement({"docling": a, "mineru": b, "marker": c})
    assert all(m["engine"] != "mineru" for m in groups[0]["members"])
    other, _ = document("mineru", file_id="supplementary")
    with pytest.raises(ValueError, match="身份"):
        complement({"docling": a, "mineru": other, "marker": c})


def test_missing_geometry_remains_unmatched_and_visible():
    a, _ = document("docling")
    b, block = document("mineru", bbox=None, kind="formula", text="x^2")
    c, _ = document("marker")
    result, groups = complement({"docling": a, "mineru": b, "marker": c})
    assert result.block(block.block_id).bbox is None
    assert any(g["alignment"] == "unmatched" and g["primary"]["block_id"] == block.block_id for g in groups)


def test_one_to_many_is_not_called_semantic_match():
    a, _ = document("docling")
    b, block = document("mineru")
    extra = block.model_copy(deep=True)
    extra.block_id = "another-block"
    extra.text = "different value 150"
    b.blocks.append(extra)
    c, _ = document("marker")
    _, groups = complement({"docling": a, "mineru": b, "marker": c})
    assert groups[0]["alignment"] == "uncertain_one_to_many"


def make_pdf(path):
    with pymupdf.open() as pdf:
        page = pdf.new_page(width=200, height=300)
        page.insert_text((10, 20), "Independent sample, no H3S.")
        pdf.save(path)


def test_case_is_replaceable_and_hash_mismatch_fails(tmp_path):
    make_pdf(tmp_path / "different.pdf")
    case = {"case_id": "different", "files": [{"file_id": "paper", "role": "main", "path": "different.pdf"}]}
    path = tmp_path / "case.json"
    path.write_text(json.dumps(case))
    validated = validate_case(path)
    assert validated["files"][0]["pages"] == 1
    assert len(validated["files"][0]["sha256"]) == 64
    case["files"][0]["sha256"] = "0" * 64
    path.write_text(json.dumps(case))
    with pytest.raises(ValueError, match="哈希"):
        validate_case(path)


def test_marker_table_spans_and_scale_preserved(tmp_path):
    path = tmp_path / "different.pdf"
    make_pdf(path)
    raw = {"runtime": {"version": "2"}, "document": {"children": [{"polygon": [[0, 0], [400, 0], [400, 600], [0, 600]],
        "children": [{"id": "table", "block_type": "Table", "polygon": [[20, 20], [200, 20], [200, 100], [20, 100]],
                      "html": '<table><tr><td rowspan="2">Phase</td><td>A</td></tr><tr><td>B</td></tr></table>'}]}]}}
    result = convert_marker(raw, DocumentSource(path, "main"), ParseOptions(profile="demo"))
    table = result.tables[0]
    assert (table.row_count, table.column_count) == (2, 2)
    assert result.block(table.block_id).bbox == (10, 10, 100, 50)
    assert result.block(table.cells[0].block_id).metadata["row_span"] == 2
    assert all(c.bbox is None for c in table.cells)
    assert table.cells[-1].column_index == 1


def test_actual_process_start_failure_retained(tmp_path):
    path = tmp_path / "paper.pdf"
    make_pdf(path)
    item = {"file_id": "main", "role": "main", "path": str(path), "sha256": "a" * 64, "pages": 1}
    result = parse_one("marker", item, tmp_path / "run", tmp_path / "missing-python", 1)
    assert result["status"] == "failed"
    assert (tmp_path / "run/marker/main/run.json").exists()
    with pytest.raises(FileExistsError):
        parse_one("marker", item, tmp_path / "run", tmp_path / "missing-python", 1)


def test_report_alignment_does_not_depend_on_state_order():
    states = [{"material": "AB", "pressure_value_gpa": 10, "note": "first"},
              {"material": "AB", "pressure_value_gpa": 20, "note": "second"}]
    left = {f["key"]: f["value"] for f in fields_for("docling", {"material_states": states})}
    right = {f["key"]: f["value"] for f in fields_for("mineru", {"material_states": states[::-1]})}
    assert left == right


def test_review_identity_changes_when_candidate_or_attempt_changes():
    first = fields_for("docling", {"attempt": "1", "paper": {"title": "A"}})[0]
    changed = fields_for("docling", {"attempt": "1", "paper": {"title": "B"}})[0]
    rerun = fields_for("docling", {"attempt": "2", "paper": {"title": "A"}})[0]
    assert len({first["id"], changed["id"], rerun["id"]}) == 3


def test_paper_enum_and_parameter_range_are_not_marked_form_ready():
    from scripts.complementary_pdf_demo.extraction import form_issues
    form = {"paper": {"superconductor_kind": "predicted"}, "material_states": [{"property_modules": [
        {"records": [{"payload": {"parameters": {"mu_star": "0.1-0.2"}}}]}]}]}
    assert {i["code"] for i in form_issues(form)} == {"invalid_superconductor_kind", "numeric_parameter_not_representable"}


def test_subpoint_geometry_rounding_does_not_lose_edge_blocks():
    a, _ = document("docling")
    b, block = document("mineru", bbox=(190, 10, 200, 30), kind="formula")
    c, _ = document("marker")
    b.pages[0].width += 0.000001
    block.bbox = (190, 10, 200.000001, 30)
    block.page_width = b.pages[0].width
    result, _ = complement({"docling": a, "mineru": b, "marker": c})
    assert result.block(block.block_id) is not None
    b.pages[0].width += 1
    with pytest.raises(ValueError, match="几何"):
        complement({"docling": a, "mineru": b, "marker": c})


def test_exact_quote_location_does_not_validate_scientific_value():
    from scripts.complementary_pdf_demo.extraction import validate_sources
    ir, block = document("docling", text="Tc = 200 K")
    raw = {"value_number": 999, "evidences": [{"file_id": "main", "pdf_page": 1, "block_id": block.block_id, "quote": "Tc = 200 K"}]}
    checks = validate_sources(raw, {"main": ir}, {("docling", "main"): ir})
    assert checks[0]["valid"] is True
    raw["evidences"][0]["quote"] = "Tc = 999 K"
    assert validate_sources(raw, {"main": ir}, {("docling", "main"): ir})[0]["valid"] is False


def test_reference_checker_rejects_correct_tc_attached_to_wrong_pressure():
    from scripts.complementary_pdf_demo.evaluate import evaluate_item
    form = {"material_states": [{"reported_space_group_symbol": "X", "pressure_value_gpa": 20,
        "property_modules": [{"records": [{"property_code": "tc", "value_kind": "number", "value_number": 9}]}]}]}
    item = {"query": {"kind": "record", "phase": "X", "pressure": 30, "path": "value"}, "expected": 9, "mode": "numbers"}
    assert evaluate_item(form, item)["status"] == "incorrect"


def test_generated_html_does_not_execute_model_supplied_markup(tmp_path):
    from bs4 import BeautifulSoup
    from scripts.complementary_pdf_demo.report import build_report
    from scripts.complementary_pdf_demo.parsers import write_json
    payload = '</script><script>alert("untrusted")</script>'
    base = tmp_path / "extractions/docling"
    write_json(base / "latest.json", {"attempt": "attempt-001"})
    write_json(base / "attempt-001/form.json", {"arm": "docling", "attempt": "attempt-001", "validation": {},
                                               "paper": {"title": payload}, "material_states": [], "status": "needs_review"})
    build_report(tmp_path, {"run_id": "test", "case": {"case_id": "test", "files": []}})
    soup = BeautifulSoup((tmp_path / "index.html").read_text(), "html.parser")
    assert len(soup.find_all("script")) == 2
    data = json.loads(soup.find("script", id="report-data").string)
    assert data["forms"]["docling"]["paper"]["title"] == payload

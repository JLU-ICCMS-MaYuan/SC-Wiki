"""四工具的真实协议与数据边界，不把纯定位当科学语义证明。"""
from __future__ import annotations

import json
import os
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("DATABASE_URL", "sqlite:////tmp/scwiki-four-tool-tests.db")
os.environ.setdefault("JWT_SECRET_KEY", "test-only-four-tool-secret")
import pytest
import pymupdf

from backend.ingest.document_ir import PageGeometry
from backend.ingest.document_parsers import DocumentSource, ParseOptions, ParserError
from backend.ingest.structured_pdf import IrBuilder, convert_docling, run_parser_worker
from backend.ingest.complementary_ir import repair_pages, compose
from backend.ingest.grobid_document import parse_document, apply_bibliography
from backend.ingest.scientific_contracts import normalize_parameters, validate_conditions
from backend.ingest.domain_extraction import structured_chunks


@pytest.mark.parametrize("mismatch", [None, "other_block", "other_file", "rewritten_quote"])
def test_explicit_quote_reference_uses_only_input_text(mismatch):
    from backend.ingest.domain_extraction import normalize_extraction
    document = ir("mineru")
    block = document.blocks[0]
    evidence = {"file_id": "paper", "pdf_page": 1, "block_id": block.block_id,
                "quote_id": block.block_id, "quote": None}
    if mismatch == "other_block": evidence["quote_id"] = "wrong"
    if mismatch == "other_file": evidence["file_id"] = "other"
    if mismatch == "rewritten_quote": evidence["quote"] = "Tc = 999 K"
    raw = {"extraction_version":"1", "material_states":[{"scope":"current_paper", "material":"H3S",
        "state_kind":"theoretical", "evidences":[evidence], "property_modules":[]}]}
    kwargs = {"allowed_blocks":{("paper",1,block.block_id)},
              "allowed_quote_text":{("paper",1,block.block_id):block.text}}
    if mismatch:
        with pytest.raises(ValueError): normalize_extraction(raw, **kwargs)
    else:
        result = normalize_extraction(raw, **kwargs)
        assert result["material_states"][0]["evidences"][0]["quote"] == block.text


def ir(engine, source=None, table=False, text="Tc = 200 K", page=1):
    source = source or DocumentSource(Path("none"), "paper", sha256="a"*64)
    builder = IrBuilder(source, ParseOptions(profile=engine), engine, "1", [PageGeometry(pdf_page=1, width=600, height=800)], "ocr" if engine=="mineru" else "text")
    block = builder.add(page, "table" if table else "paragraph", text, (20, 20, 500, 100))
    if table:
        cells = [(0, 0, "150 GPa", (20, 20, 100, 100) if engine=="docling" else None, {"row_span":2,"column_span":1}),
                 (0, 1, text, (100, 20, 500, 100) if engine=="docling" else None, {"row_span":1,"column_span":1})]
        builder.table(block, 2, 2, cells)
    return builder.finish()


def test_mineru_is_primary_and_selected_table_keeps_all_original_candidates():
    a,b=ir("mineru",table=True),ir("docling",table=True,text="Tc = 199 K")
    result=compose({"mineru":a,"docling":b})
    route=result.coverage["routing"][0]
    assert route["engine"]=="docling" and route["alternatives"]
    assert result.block(a.blocks[0].block_id).text=="Tc = 200 K"
    assert result.block(b.blocks[0].block_id).metadata["selected_for_reading"]
    assert route["alternatives"][0]["text"] == "Tc = 200 K"
    chunks=structured_chunks(result)
    assert "199 K" in chunks[0].content and "200 K" not in chunks[0].content
    cells=json.loads(chunks[0].content)["pages"][0]["blocks"]
    assert any(c["metadata"].get("row_span")==2 for c in cells)


def test_plain_body_uses_only_mineru_and_needs_no_other_engines():
    result=compose({"mineru":ir("mineru"),"marker":ir("marker",text="wrong 999 K")})
    assert repair_pages(ir("mineru"))["marker"]==[]
    assert "999" not in structured_chunks(result)[0].content
    assert result.coverage["routing"][0]["engine"]=="mineru"


def test_different_source_cannot_be_combined():
    other=DocumentSource(Path("none"),"another",sha256="b"*64)
    with pytest.raises(ValueError,match="身份"):
        compose({"mineru":ir("mineru"),"docling":ir("docling",other)})


def test_grobid_header_is_not_a_reference_and_citation_target_is_preserved():
    xml='''<TEI xmlns="http://www.tei-c.org/ns/1.0"><teiHeader><fileDesc><titleStmt><title>Main</title></titleStmt><sourceDesc><biblStruct><analytic><title>Main</title><author><persName><forename>Ada</forename><surname>Lovelace</surname></persName></author></analytic><idno type="DOI">10.1000/main</idno></biblStruct></sourceDesc></fileDesc></teiHeader><text><body><p>Prior work <ref type="bibr" target="#b0" coords="2,10,20,30,40">[1]</ref></p></body><back><listBibl><biblStruct xml:id="b0"><analytic><title>Reference</title></analytic></biblStruct></listBibl></back></text></TEI>'''
    result=parse_document(xml)
    assert result["metadata"]["title"]=="Main" and result["metadata"]["authors"]==["Ada Lovelace"]
    assert len(result["references"])==1 and result["references"][0]["title"]=="Reference"
    assert result["citations"][0]["targets"]==["#b0"]
    assert parse_document(xml.replace('<listBibl><biblStruct xml:id="b0"><analytic><title>Reference</title></analytic></biblStruct></listBibl>',""))["references"]==[]


def test_bibliography_preserves_conflicts_but_not_model_generated_values():
    draft={"paper":{"title":"model title","paper_type":"theoretical"}}
    apply_bibliography(draft,{"status":"succeeded","metadata":{"title":"Original"},"metadata_sources":{"title":{"xpath":"header"}},
                             "file_id":"f","source_sha256":"a"*64,"parser_version":"0.8.1"})
    assert draft["paper"]["title"]=="Original" and draft["paper"]["paper_type"]=="theoretical"
    assert draft["bibliography_conflicts"][0]["extracted_value"]=="model title"


def test_parameter_range_is_an_extension_not_an_endpoint():
    record={"payload":{"parameters":{"mu_star":"0.10–0.13","omega_log":"1200 K"}}}
    normalize_parameters(record)
    p=record["payload"]["parameters"]
    assert "mu_star" not in p and p["omega_log"]==1200
    extension=next(x for x in p["extensions"] if x["key"]=="mu_star")
    assert (extension["value_min"],extension["value_max"],extension["value_raw"])==(.1,.13,"0.10–0.13")


@pytest.mark.parametrize("payload",[{"pressure_gpa":300},{}])
def test_pressure_wrongly_attached_to_state_is_rejected(payload):
    record={"property_code":"tc","value_number":179,"payload":{"calculation_conditions":payload},
            "evidences":[{"quote":"179 K at 300 GPa"}]}
    with pytest.raises(ValueError,match="压力"):
        validate_conditions({"pressure_value_gpa":200},record)
    validate_conditions({"pressure_value_gpa":300},record)


def test_explicit_bandgap_pressure_cannot_be_missing_or_wrong():
    record = {"property_code":"band_gap", "value_number":3.34, "payload":{},
              "evidences":[{"quote":"an indirect band gap of 3.34 eV at 20 GPa"}]}
    for pressure in (None, 200):
        with pytest.raises(ValueError, match="压力"):
            validate_conditions({"pressure_value_gpa":pressure}, record)
    validate_conditions({"pressure_value_gpa":20}, record)
    record["evidences"][0]["quote"] += "; 3.34 eV at 30 GPa"
    for pressure in (None, 200):
        with pytest.raises(ValueError, match="压力"):
            validate_conditions({"pressure_value_gpa":pressure}, record)
    validate_conditions({"pressure_value_gpa":30}, record)


def test_explicit_pressure_binding_splits_only_proven_records_and_preserves_original():
    from backend.ingest.scientific_contracts import resolve_reported_pressures
    records = [{"property_code":"tc", "value_number":tc, "evidences":[{
        "block_id":"source", "quote":f"{tc} K at {pressure} GPa"}]} for tc,pressure in [(201,200),(187,250)]]
    result = {"material_states":[{"material":"CaH6", "pressure_value_gpa":None, "pressure_raw":"stable above 150 GPa", "evidences":[],
        "property_modules":[{"module_code":"superconductive_properties", "records":records}]}]}
    resolve_reported_pressures(result)
    assert [s["pressure_value_gpa"] for s in result["material_states"]] == [200,250]
    assert all(b["original_pressure_raw"] == "stable above 150 GPa" for b in result["_pressure_bindings"])
    assert [s["property_modules"][0]["records"][0]["value_number"] for s in result["material_states"]] == [201,187]


def test_docling_subset_maps_back_to_original_page(tmp_path):
    path=tmp_path/"three.pdf"
    with pymupdf.open() as pdf:
        for _ in range(3):pdf.new_page(width=600,height=800)
        pdf.save(path)
    raw={"mode":"text","page_map":[3],"document":{"pages":{"1":{"size":{"width":600,"height":800}}},
         "body":{"children":[{"$ref":"#/texts/0"}]},"texts":[{"self_ref":"#/texts/0","label":"text","text":"last page",
         "prov":[{"page_no":1,"bbox":{"l":20,"t":20,"r":100,"b":60,"coord_origin":"TOPLEFT"}}]}]}}
    result=convert_docling(raw,DocumentSource(path,"f"),ParseOptions(profile="docling"),"1")
    assert result.blocks[0].pdf_page==3


def test_actual_timeout_keeps_logs_and_run_state(tmp_path):
    path=tmp_path/"one.pdf"
    with pymupdf.open() as pdf:pdf.new_page();pdf.save(path)
    output=tmp_path/"artifacts"
    with pytest.raises(ParserError) as caught:
        run_parser_worker("mineru",path,ParseOptions(profile="complementary",parser_options={"artifact_directory":str(output),"timeout_seconds":.001}))
    assert caught.value.code=="parser_timeout"
    assert (output/"run.json").exists() and (output/"stderr.log").exists()


def test_actual_cancel_stops_worker_and_keeps_diagnostics(tmp_path):
    path = tmp_path / "one.pdf"
    with pymupdf.open() as pdf:
        pdf.new_page()
        pdf.save(path)
    output = tmp_path / "cancelled"
    with pytest.raises(ParserError) as caught:
        run_parser_worker("mineru", path, ParseOptions(profile="complementary", cancelled=lambda: True,
            parser_options={"artifact_directory": str(output)}))
    assert caught.value.code == "parser_cancelled"
    assert json.loads((output / "run.json").read_text())["exit_code"] is not None


def test_grobid_unavailable_preserves_artifact_without_inventing_metadata(tmp_path, monkeypatch):
    from backend.ingest.grobid_document import extract_document
    path = tmp_path / "one.pdf"
    path.write_bytes(b"test PDF")
    monkeypatch.setenv("GROBID_URL", "http://127.0.0.1:1")
    result = extract_document(DocumentSource(path, "f"), tmp_path / "grobid", timeout=.1)
    assert result["status"] == "unavailable" and result["metadata"] == {}
    assert (tmp_path / "grobid/document.json").exists()


def test_api_rejects_new_alternative_profiles_and_reads_old_task(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from backend.api import upload_tasks as api
    from backend.ingest import upload_tasks
    from backend.security import get_current_user
    app = FastAPI()
    app.include_router(api.router)
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=1, role="user", is_approved=True)
    app.dependency_overrides[api.request_llm_config] = lambda: None
    monkeypatch.setattr(upload_tasks, "get_state", lambda _: {
        "task_id": "old", "user_id": 1, "state_schema_version": 1, "parser_profile": "layout", "status": "ready"})
    with TestClient(app) as client:
        files = [{"client_id":"main", "role":"main", "filename":"paper.pdf", "size":10}]
        for profile in ("legacy", "text", "layout", "ocr"):
            assert client.post("/api/upload-tasks", json={"files": files, "parser_profile": profile}).status_code == 422
        assert client.get("/api/upload-tasks/old").json()["data"]["parser_profile"] == "layout"


@pytest.mark.parametrize("finish", ["stop", "length"])
def test_deepseek_request_disables_thinking_and_rejects_truncation(monkeypatch, finish):
    from backend.rag import llm
    captured = {}
    def create(**kwargs):
        captured.update(kwargs)
        return [SimpleNamespace(usage=None, choices=[SimpleNamespace(
            delta=SimpleNamespace(content='{"value": 1}'), finish_reason=finish)])]
    monkeypatch.setattr(llm, "get_llm_config", lambda: SimpleNamespace(model="deepseek-v4-pro"))
    monkeypatch.setattr(llm, "_client", lambda _: SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create))))
    responses = []
    events = []
    if finish == "stop":
        assert llm.complete_json("system", "input", retries=0, on_partial=responses.append, on_call=events.append) == {"value":1}
    else:
        with pytest.raises(RuntimeError):
            llm.complete_json("system", "input", retries=0, on_partial=responses.append, on_call=events.append)
    assert captured["extra_body"] == {"thinking":{"type":"disabled"}}
    assert captured["max_tokens"] == 65536 and responses == ['{"value": 1}']
    assert events[0]["status"] == ("completed" if finish == "stop" else "failed")
    assert events[0]["thinking"] == "disabled" and events[0]["finish_reason"] == finish


def test_each_model_retry_keeps_its_own_response_and_does_not_reuse_partial_text(tmp_path, monkeypatch):
    from backend.rag import llm, llm_context
    from backend.ingest import upload_jobs
    from backend.ingest.chunker import Chunk
    from openai import APIConnectionError
    import httpx
    config = SimpleNamespace(provider="test", model="deepseek-v4-pro", base_url="http://unused")
    monkeypatch.setattr(llm, "get_llm_config", lambda: config)
    monkeypatch.setattr(llm_context, "get_llm_config", lambda: config)
    monkeypatch.setattr(llm.time, "sleep", lambda _: None)
    monkeypatch.setattr(upload_jobs, "_chunk_result_path", lambda *_: tmp_path / "chunk.json")
    from backend.storage import paths
    monkeypatch.setattr(paths, "object_mode", lambda: False)
    attempts = 0
    valid = '{"extraction_version":"1","material_states":[]}'
    def create(**_):
        nonlocal attempts
        attempts += 1
        if attempts == 2:
            raise APIConnectionError(request=httpx.Request("POST", "http://unused"))
        return [SimpleNamespace(usage=None, choices=[SimpleNamespace(
            delta=SimpleNamespace(content="{invalid" if attempts == 1 else valid), finish_reason="stop")])]
    monkeypatch.setattr(llm, "_client", lambda _: SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create))))
    chunk = Chunk(paper_id=0, chunk_index=0, section_name="Document IR", heading=None,
                  content=json.dumps({"file_id":"f", "pages":[]}), token_count=1)
    upload_jobs._read_chunk("task", chunk, "f", {"kind":"pdf", "parser_profile":"complementary"})
    directory = next((tmp_path / "extraction_attempts/chunk").iterdir())
    assert (directory / "call-1.response.txt").read_text() == "{invalid"
    assert not (directory / "call-2.response.txt").exists()
    assert (directory / "call-3.response.txt").read_text() == valid
    assert [json.loads((directory / f"call-{n}.json").read_text())["status"] for n in (1,2,3)] == ["failed","failed","completed"]

"""全文范围材料排除，不能误删跨文件已有具体Tc或在建卡时重新引入。"""
from copy import deepcopy
import json

import pytest

from backend.ingest import parsing_workflows as workflows


def answer(materials):
    return dict(paper_type="theoretical", theoretical_subtype="calculation",
        superconductor_kind="conventional", reason="本文计算材料的电声耦合和临界温度",
        source_ids=["review-source-0"], contribution_source_ids=["review-source-0"],
        tc_materials=materials, paper={})


def material(name="LaH9", specific=False, ranged=True, source="review-source-0"):
    return dict(material=name, has_specific_tc=specific, has_range_tc=ranged,
                source_ids=[source], reason="仅有Tc上界，未报告具体数值" if not specific else "本文明确报告具体Tc")


SOURCE = dict(file_id="main", file_role="main", chunk_index=0,
              content="We calculate Tc for YH10 and report Tc below 56 K for LaH9.", section_role="result")


def test_workflow_preserves_source_backed_range_only_exclusion():
    report = workflows.assess([SOURCE], complete=lambda *_a, **_kw: answer([material()]))
    scope = report.get("tc_material_scope") or {}
    assert [x["material"] for x in scope.get("excluded_materials", [])] == ["LaH9"]
    assert scope["excluded_materials"][0]["evidences"][0]["file_id"] == "main"


def test_concrete_tc_in_si_prevents_whole_material_exclusion(monkeypatch):
    from backend.ingest import property_evidence
    monkeypatch.setattr(property_evidence, "SOURCE_BATCH_CHARS", 20)
    sources = [SOURCE, {**SOURCE, "file_id": "si", "file_role": "supplementary", "content": "LaH9 has Tc 52 K."}]
    calls = []
    def model(_prompt, body, **_kwargs):
        payload = json.loads(body); calls.append(payload)
        if "sources" in payload and payload["sources"][0]["file_id"] == "si":
            return answer([material(specific=True, ranged=False, source="review-source-1")])
        return answer([material()])  # 汇总遗漏SI的具体值也不能抹掉已读事实。
    report = workflows.assess(sources, complete=model)
    assert len(calls) == 3
    assert report.get("tc_material_scope", {}).get("excluded_materials") == []


def test_scope_with_forged_sources_does_not_silently_discard_material():
    report = workflows.assess([SOURCE], complete=lambda *_a, **_kw: answer([material(source="invented")]))
    assert report["status"] != "matched"


def test_unquantified_figure_or_missing_tc_is_not_range_only():
    entries = [material(name="YH6", specific=False, ranged=False),
               material(name="LaH6", specific=False, ranged=False), material()]
    report = workflows.assess([SOURCE], complete=lambda *_a, **_kw: answer(entries))
    scope = report["tc_material_scope"]
    assert len(scope["materials"]) == 3
    assert [item["material"] for item in scope["excluded_materials"]] == ["LaH9"]


def test_inventory_cannot_reintroduce_excluded_material():
    from backend.ingest.state_inventory import apply_inventory, FIELDS
    draft = {"material_states": []}
    response = {"states": [{"values": {k: "LaH9" if k == "material" else None for k in FIELDS},
        "source_ids": ["inventory-source-0"], "reason": "结构表报告此材料"}], "assignments": [], "record_assignments": []}
    scope = {"excluded_materials": [material()]}
    before = deepcopy(draft)
    with pytest.raises(ValueError, match="排除"):
        apply_inventory(draft, [{"source_id": "inventory-source-0", "file_id": "main", "content": "LaH9"}],
                        response, material_scope=scope)
    assert draft == before


def test_excluded_extraction_fails_before_value_validation_without_retry(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from backend.ingest import upload_jobs as jobs
    from backend.ingest.chunker import Chunk
    from backend.rag import llm_context
    from backend.rag.structured_output import StructuredOutputError
    scope = {"excluded_materials": [material()]}
    context = {"file_id": "main", "pages": [{"geometry": {"pdf_page": 1},
        "blocks": [{"pdf_page": 1, "block_id": "b", "text": "LaH9 Tc below 56 K."}]}]}
    chunk = Chunk(0, 0, "正文", None, json.dumps(context), 10)
    monkeypatch.setattr(jobs, "_chunk_result_path", lambda *_a, **_kw: tmp_path / "00000.json")
    monkeypatch.setattr(llm_context, "get_llm_config", lambda: SimpleNamespace(
        model="fixture", provider="isolated", base_url="https://model.invalid"))
    calls = []
    def model(prompt, body, **options):
        calls.append(prompt)
        assert "WHOLE-PAPER MATERIAL SCOPE" in prompt
        return {"material_states": [{"material": "LaH9"}]}
    monkeypatch.setattr(jobs, "complete_json", model)
    with pytest.raises(StructuredOutputError, match="排除"):
        jobs._read_chunk("isolated", chunk, "main", {
            "kind": "pdf", "parser_profile": "complementary", "tc_material_scope": scope})
    assert len(calls) == 1
    assert len(list(tmp_path.rglob("raw.json"))) == 1
    assert not (tmp_path / "00000.json").exists()


def test_unassigned_scope_excluded_inventory_state_is_archived_without_losing_real_candidates():
    from backend.ingest.state_inventory import plan_states,FIELDS
    allowed={"material":"YH10","state_key":"kept-state","property_modules":[]}
    draft={"material_states":[deepcopy(allowed)]}
    source="YH10 has Tc 303 K at 400 GPa. PrH9 only below 56 K; Table also lists PrH9 geometry."
    def state(name,pressure):
        return {"values":{k:name if k=="material"else pressure if k=="pressure_value_gpa"else None for k in FIELDS},
          "source_ids":["inventory-source-0"],"reason":"原文状态"}
    response={"states":[state("PrH9",100),state("YH10",400)],
      "assignments":[{"candidate_state_key":"kept-state","target_index":1,"status":"supported","reason":"原候选仍在YH10","source_ids":["inventory-source-0"]}],
      "record_assignments":[]}
    seen=[]
    plan_states(draft,[{"file_id":"main","content":source}],lambda *_a,**_k:deepcopy(response),
      material_scope={"excluded_materials":[material(name="PrH9")]},on_response=seen.append)
    assert [s["material"]for s in draft["material_states"]]==["YH10"]
    trace=seen[0]["scope_exclusions"][0]
    assert trace["state"]==response["states"][0] and trace["sources"][0]["content"]==source
    assert trace["reason"] and trace["scope_decision"]["material"]=="PrH9"


def test_scope_excluded_inventory_cannot_drop_any_assigned_candidate():
    from backend.ingest.state_inventory import plan_states,FIELDS
    draft={"material_states":[{"material":"YH10","state_key":"kept-state","property_modules":[]}]};before=deepcopy(draft)
    response={"states":[{"values":{k:"PrH9"if k=="material"else None for k in FIELDS},
      "source_ids":["inventory-source-0"],"reason":"错误目标"}],
      "assignments":[{"candidate_state_key":"kept-state","target_index":0,"status":"supported","reason":"不能丢失原候选","source_ids":["inventory-source-0"]}],"record_assignments":[]}
    with pytest.raises(ValueError):
        plan_states(draft,[{"file_id":"main","content":"YH10 and PrH9."}],lambda *_a,**_k:response,
          material_scope={"excluded_materials":[material(name="PrH9")]})
    assert draft==before

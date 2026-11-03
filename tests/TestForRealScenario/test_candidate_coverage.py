"""#210：同一份真实候选贯穿整理、最终门和既有科学核对，禁止局部通过冒充完成。"""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path

import pytest


def inputs():
    path = Path(__file__).with_name("verify_filling_summary.py")
    spec = importlib.util.spec_from_file_location("h3s_replay", path)
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    data, states = helper.replay_inputs()
    response = deepcopy(data["response"])
    response.pop("candidate_relations", None)
    return data, states, response


def documents(data):
    from backend.ingest.document_ir import DocumentIR, DocumentBlock, PageGeometry, content_hash
    result = {}
    for source in data["sources"]:
        file_id = source["file_id"]
        if file_id not in result:
            own = [s for s in data["sources"] if s["file_id"] == file_id]
            result[file_id] = DocumentIR(document_id=file_id, source_file_id=file_id,
                source_sha256=source["source_sha256"], parse_profile="complementary",
                parser={"name": source.get("parser", "complementary"), "version": source.get("parser_version", "1"), "mode": "text"},
                pages=[PageGeometry(pdf_page=n, width=600, height=800) for n in sorted({s["page_start"] for s in own})],
                blocks=[DocumentBlock(block_id=s["block_id"], block_type="paragraph", pdf_page=s["page_start"],
                    reading_order=i, text=s["content"], content_hash=content_hash(s["content"])) for i, s in enumerate(own)])
    return result


def test_original_response_uses_existing_dispositions_through_final_gate(tmp_path):
    from backend.ingest.scientific_form_filling import apply_plan
    data, states, response = inputs()
    result, audit = apply_plan(states, data["sources"], response)
    from backend.ingest.scientific_form_filling import validate_filling_coverage
    validate_filling_coverage(states, result, audit)
    assert len(audit["candidate_dispositions"]) == 5
    assert sum(len(m["records"]) for s in result for m in s["property_modules"]) == 4
    file = tmp_path / "roundtrip.json"
    file.write_text(json.dumps({"states": result, "report": audit}))
    restored = json.loads(file.read_text())
    validate_filling_coverage(states, restored["states"], restored["report"])
    assert restored == {"states": result, "report": audit}


def test_production_claim_gate_accepts_merge_but_still_catches_loss_before_organization():
    from backend.ingest.scientific_form_filling import apply_plan
    from backend.ingest.document_claims import claims_from_candidates, missing_tc_measurements, missing_tc_after_filling
    data, states, response = inputs()
    result, audit = apply_plan(states, data["sources"], response)
    docs = documents(data)
    before = claims_from_candidates({"material_states": states}, docs)
    after = claims_from_candidates({"material_states": result}, docs)
    assert len(missing_tc_measurements(before, after, allow_paired_range=True)) == 1
    assert not missing_tc_after_filling(before, after, input_states=states, output_states=result,
        filling_report={**audit, "status": "completed"}, documents=docs)
    # 确定性组装若已漏184 K，后续完整去向不能替它掩盖。
    lost = deepcopy(states)
    lost[2]["property_modules"][0]["records"] = []
    answer = deepcopy(response)
    answer["records"] = [r for r in answer["records"] if "s2:m0:r0" not in r["candidate_ids"]]
    filled, report = apply_plan(lost, data["sources"], answer)
    assert missing_tc_after_filling(before, after, input_states=lost, output_states=filled,
        filling_report={**report, "status": "completed"}, documents=docs)


@pytest.mark.parametrize("mutation", ["lost_candidate", "lost_target", "wrong_state", "lost_source", "stale_original"])
def test_complete_mapping_cannot_hide_actual_loss(mutation):
    from backend.ingest.scientific_form_filling import apply_plan, validate_filling_coverage
    data, states, response = inputs()
    result, audit = apply_plan(states, data["sources"], response)
    if mutation == "lost_candidate":
        audit["candidate_dispositions"].pop("s2:m0:r0")
    elif mutation == "lost_target":
        result[2]["property_modules"][0]["records"] = []
    elif mutation == "wrong_state":
        moved = result[2]["property_modules"][0]["records"].pop()
        result[1]["property_modules"][0]["records"].append(moved)
    elif mutation == "lost_source":
        result[1]["property_modules"][0]["records"][0]["evidences"] = []
    else:
        audit["candidate_dispositions"]["s1:m0:r1"]["original_record"]["value_number"] = 201
    with pytest.raises(ValueError):
        validate_filling_coverage(states, result, audit)


@pytest.mark.parametrize("verdict", ["supported", "unsupported"])
def test_existing_review_checks_originals_and_does_not_trust_mapping(monkeypatch, verdict):
    from backend.ingest.scientific_form_filling import apply_plan
    from backend.ingest import model_review
    from backend.ingest.property_evidence import digest
    from backend.ingest.field_review import reusable
    data, states, response = inputs()
    result, audit = apply_plan(states, data["sources"], response)
    draft = {"paper": {}, "material_states": result,
             "form_filling_report": {**audit, "status": "completed"}}
    target = result[1]["property_modules"][0]["records"][0]
    calls = []
    def model(_, prompt, **kwargs):
        request = json.loads(prompt)
        row = request["records"][0]
        originals = row["organization_context"]
        assert {v["original_record"].get("value_number") for v in originals} == {None, 200.0}
        assert all(v["reasons"] for v in originals)
        calls.append(request)
        return {"results": [{"key": row["key"], "status": verdict,
            "source_ids": [request["sources"][0]["source_id"]],
            "reason": "已结合双方原文核实合并关系。" if verdict == "supported" else "原文是独立结果，不能合并。"}]}
    original_review = model_review.review_fields
    monkeypatch.setattr(model_review, "review_fields", lambda *a, **kw: original_review(*a, model=model, **kw))
    def rebuild(current):
        return {"records": [{"key": "tc", "item_key": "tc", "field": "material_states[1].property_modules[0].records[0].value_min",
            "kind": "field", "record_key": target["record_key"], "record_field": "value_min",
            "current_value": 191, "required": True, "claim": {"value": 191},
            "content_hash": digest(191), "source_hash": "original-pdf", "state_review_context": None}],
            "chunks": [{"file_id": "main", "content": data["sources"][0]["content"]}]}
    current, snapshot, results, report = model_review.review_draft(draft, rebuild, model_name="isolated")
    assert results["tc"]["status"] == verdict
    assert not results["tc"].get("human_confirmed")
    assert len(calls) == 1
    assert reusable(snapshot["records"][0], results["tc"])
    model_review.review_draft(current, rebuild, model_name="isolated", initial_results=results)
    assert len(calls) == 1

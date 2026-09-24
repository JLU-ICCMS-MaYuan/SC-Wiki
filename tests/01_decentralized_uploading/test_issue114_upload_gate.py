"""执行新解析任务到终态，模型用确定响应，PDF/IR/Claim/覆盖校验走真实代码。"""
import copy
import json

import pytest
from backend.ingest import upload_jobs
from backend.ingest.document_parsers import ParserError


@pytest.mark.parametrize("valid", [True,False])
def test_upload_pipeline_never_reports_ready_with_unlocated_claim(tmp_path,monkeypatch,valid):
    import pymupdf
    from backend.ingest import property_evidence
    text="LaH10 has a critical temperature of 200 K at 150 GPa. This result is directly reported."
    path=tmp_path/"paper.pdf"
    with pymupdf.open() as pdf:
        page=pdf.new_page();page.insert_textbox(pymupdf.Rect(40,40,550,200),text,fontsize=12);pdf.save(path)
    task="a"*32
    artifacts=tmp_path/"artifacts";artifacts.mkdir()
    markdown=tmp_path/"markdown"/f"{task}.md";markdown.parent.mkdir()
    state={"task_id":task,"status":"queued","stage":"queued","file_path":str(path),"filename":"paper.pdf",
           "file_kind":"pdf","file_sha256":upload_jobs.sha256_file(path),"parser_profile":"text","user_id":1}
    def update(_,**changes): state.update(changes);return dict(state)
    monkeypatch.setattr(upload_jobs,"get_state",lambda _:dict(state))
    monkeypatch.setattr(upload_jobs,"update_state",update)
    monkeypatch.setattr(upload_jobs,"_find_existing_by_hash",lambda _:None)
    monkeypatch.setattr(upload_jobs,"_find_existing_paper",lambda _:None)
    monkeypatch.setattr(upload_jobs,"markdown_path",lambda _:markdown)
    monkeypatch.setattr(upload_jobs,"artifact_directory",lambda _:artifacts)
    monkeypatch.setattr(upload_jobs,"artifact_path",lambda _:artifacts/"result.json")
    monkeypatch.setattr(upload_jobs,"data_path",lambda _:markdown.parent)
    monkeypatch.setattr(upload_jobs,"extract_references_from_pdf",lambda _:{"status":"unavailable","references":[]})
    monkeypatch.setattr(upload_jobs,"extract_structure_candidates",lambda *a,**k:[])
    monkeypatch.setattr(upload_jobs,"_schedule_terminal_cleanup",lambda _:None)
    monkeypatch.setattr(property_evidence,"generate_upload_suggestions",lambda *a,**k:None)
    saved=[];monkeypatch.setattr(upload_jobs,"save_draft",lambda _,value:saved.append(value))
    material={"scope":"current_paper","material":"LaH10","pressure_value_gpa":150,"state_kind":"theoretical",
              "evidence":{"file_id":"main","page":1,"quote":text},
              "tc_results":[{"tc_value_k":200,"tc_method":"unknown","result_kind":"theoretical",
                 "evidence":{"file_id":"main","page":1,"quote":"200 K" if valid else "999 K"}}]}
    calls=[]
    def complete(system,prompt,**kwargs):
        calls.append(system)
        if system.startswith("Repair"):
            return {"done":True}
        from backend.ingest.domain_extraction import DOMAIN_SYSTEM_PROMPT
        if system == DOMAIN_SYSTEM_PROMPT:
            context = json.loads(prompt[prompt.index("{"):])
            block = context["pages"][0]["blocks"][0]
            evidence = {"file_id":"main","pdf_page":1,"block_id":block["block_id"],"quote":text}
            return {"extraction_version":"1","metadata":{"title":"Paper"},"material_states":[{
                "scope":"current_paper","material":"LaH10","state_kind":"theoretical","pressure_value_gpa":150,
                "evidences":[evidence],"property_modules":[{"module_code":"superconductive_properties","records":[{
                    "module_code":"superconductive_properties","record_type":"predicted_tc","property_code":"tc",
                    "name_raw":"critical temperature","value_kind":"number","value_number":200,
                    "value_raw":"200 K","canonical_unit":"K","method_code":"unknown",
                    "payload":{"calculation_conditions":{}},"evidences":[evidence | {"quote":"200 K" if valid else "999 K"}],
                }]}],
            }]}
        if system==upload_jobs.CHUNK_SYSTEM_PROMPT:
            return {"metadata":{"title":"Paper"},"material_states":[copy.deepcopy(material)]}
        return {"paper":{"title":"Paper","paper_type":"theoretical","year":2026},"material_states":[copy.deepcopy(material)]}
    monkeypatch.setattr(upload_jobs,"complete_json",complete)
    if valid:
        result=upload_jobs._process_upload_task(task)
        assert result["status"]=="ready"
        assert result["reading_state"]=="coverage_checked"
        assert saved
        record=saved[0]["material_states"][0]["property_modules"][0]["records"][0]
        assert record["method_code"] == "unknown" and record["value_number"] == 200
        assert json.loads((artifacts/"final_claims.json").read_text())
    else:
        with pytest.raises(ParserError,match="无法定位"):
            upload_jobs._process_upload_task(task)
        assert state["status"]=="failed"
        assert state["reading_state"]=="needs_review"
        assert not saved
        assert upload_jobs.SUMMARY_SYSTEM_PROMPT not in calls
    assert (artifacts/"claims.json").is_file()
    assert (artifacts/"coverage.json").is_file()

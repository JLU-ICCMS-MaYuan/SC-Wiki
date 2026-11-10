"""四类资料同字段输入、独立条数和真实worker读取回执，全部隔离。"""
import io,json
from contextlib import contextmanager
from types import SimpleNamespace
import pytest
from PIL import Image
from backend import database
from backend.ingest import manual_evidence as manual,property_evidence as ev,upload_tasks
from backend.ingest.manual_links import validate_url
from backend.rag import llm
from test_sidebar_pdf_evidence import context,pdf_bytes
from test_evidence_progress import progress_redis

def png():
    buf=io.BytesIO();Image.new("RGB",(5,5),"white").save(buf,format="PNG");return buf.getvalue()

def test_per_type_counts_and_one_long_text(context,monkeypatch):
    factory,snap,before=context
    addresses=[f"https://example.com/evidence/{i}" for i in range(10)]
    with factory.begin() as db:
        row=manual.save_explanation(db,snap,before,"graph",7,reason="明确依据",no_evidence_reason="",
            text_items=[{"text":"Long evidence. "*2500,"source_description":"原文摘录"}],link_items=addresses)
        assert len(row["items"])==11
        for i in range(10):row=manual.add_file(db,snap,before,"graph",7,filename=f"figure{i}.png",raw=png(),source_description="")
        assert len(row["items"])==21
        with pytest.raises(manual.ManualEvidenceError):manual.add_file(db,snap,before,"graph",7,filename="eleven.png",raw=png(),source_description="")
        with pytest.raises(manual.ManualEvidenceError):
            manual.save_explanation(db,snap,before,"graph",7,reason="明确依据",no_evidence_reason="",text_items=[],link_items=addresses+["https://example.com/eleven"])
        with pytest.raises(manual.ManualEvidenceError):
            manual.save_explanation(db,snap,before,"graph",7,reason="明确依据",no_evidence_reason="",text_items=[{"text":"a","source_description":"a"},{"text":"b","source_description":"b"}])

@pytest.mark.parametrize("outcome",["supported","unsupported","failure","cancelled"])
def test_four_sources_reach_worker_and_receipt_only_on_actual_delivery(context,progress_redis,monkeypatch,outcome):
    factory,snap,before=context
    monkeypatch.setattr("backend.ingest.manual_links.read_public_link",lambda url:"Linked paper supports CaH6.")
    with factory.begin() as db:
        row=manual.save_explanation(db,snap,before,"graph",7,reason="结合原文和补充材料",no_evidence_reason="",
            text_items=[{"text":"Independent textual evidence for CaH6.","source_description":"原文摘录"}],
            link_items=["https://example.com/article"])
        manual.add_file(db,snap,before,"graph",7,filename="evidence.pdf",raw=pdf_bytes(10)[0],source_description="")
        row=manual.add_file(db,snap,before,"graph",7,filename="figure.png",raw=png(),source_description="")
    from backend.ingest.field_review import bind_support_versions
    with factory() as db:bind_support_versions(snap,db)
    monkeypatch.setattr(database,"SessionLocal",factory)
    monkeypatch.setattr(upload_tasks,"redis_client",lambda:progress_redis)
    monkeypatch.setattr(upload_tasks,"load_llm_config",lambda _:SimpleNamespace(model="isolated226"))
    monkeypatch.setattr(upload_tasks,"delete_llm_config",lambda _:None)
    @contextmanager
    def lock(_):yield
    monkeypatch.setattr(upload_tasks,"upload_task_lock",lock)
    monkeypatch.setattr(ev,"upload_snapshot",lambda *a,**k:snap)
    identity="226"+"0"*29;calls=[]
    def model(_,payload,**kwargs):
        data=json.loads(payload);calls.append(data)
        items=data["human_provided_evidence"]["graph"]["items"]
        assert {i["kind"] for i in items}=={"text","url","pdf","image"}
        assert next(i for i in items if i["kind"]=="url")["content"]=="Linked paper supports CaH6."
        assert kwargs["images"]
        if outcome=="failure":raise TimeoutError("固定故障")
        if outcome=="cancelled":ev.update_job(identity,status="cancelled")
        return {"results":[{"key":"graph","status":"unsupported" if outcome=="unsupported" else "supported",
            "reason":"结合原文与四类人工资料核对","source_ids":[data["sources"][0]["source_id"]],"basis_kind":"paper_synthesis"}]}
    monkeypatch.setattr(llm,"complete_json",model)
    job={"id":identity,"owner":7,"status":"queued","snapshot":snap,"cached":{},"purpose":"field"}
    progress_redis.set(ev.task_key(identity),json.dumps(job));ev.write_job_control(job)
    ev.run_evidence_job(identity)
    assert calls
    with factory() as db:
        loaded=db.get(manual.ScientificManualEvidence,row["id"])
        delivered=outcome in {"supported","unsupported"}
        assert all(i["ai_read_status"]==("read" if delivered else "not_read") for i in loaded.items)
        link=next(i for i in loaded.items if i["kind"]=="url")
        assert bool(link.get("link_snapshot"))==delivered

@pytest.mark.parametrize("url",["file:///etc/hosts","https://name:secret@example.com/","http://127.0.0.1/","http://169.254.169.254/"])
def test_link_reader_rejects_nonpublic_or_credential_urls(url):
    with pytest.raises(ValueError):validate_url(url,resolve=True)

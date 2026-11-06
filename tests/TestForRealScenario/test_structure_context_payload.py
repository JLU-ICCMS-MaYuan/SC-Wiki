"""原页上下文重复发送；必须保留完整来源、图片与原生回执身份。"""
import hashlib,importlib.util,json,os
from types import SimpleNamespace
from pathlib import Path
import pytest

@pytest.fixture
def reader():
    path=os.environ.get("SCWIKI_STRUCTURE_CONTEXT_CANDIDATE")
    if path:
        spec=importlib.util.spec_from_file_location("backend.ingest._context_candidate",path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
    from backend.ingest import structure_reading
    return structure_reading

def test_real_reader_sends_read_rows_once_and_keeps_images_and_native_ids(tmp_path,reader):
    import pymupdf
    path=tmp_path/"source.pdf"
    with pymupdf.open() as pdf:
        pdf.new_page().insert_text((40,40),"Original source row\nSecond original row");pdf.save(path)
    source=dict(file_id="pdf",filename="source.pdf",role="main",sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    requests=[];events=[]
    def model(prompt,body,**options):
        data=json.loads(body);requests.append(data)
        if len(requests)==1:
            args={"file_id":"pdf","page":1}
            return {"action":{"name":"read_original_page","arguments":args},
                "_tool_call":{"id":"native-context-read","type":"function","function":{"name":"read_original_page","arguments":json.dumps(args)}}}
        known={r["source_id"] for r in data["sources"]}
        assert not known.intersection(r["source_id"] for r in data["source_index"]), "已读来源不能在索引再复制"
        assert [r["content"] for r in data["sources"]]==[r["content"] for r in requests[0]["sources"]]
        history=options["tool_history"]
        assert history[0]["tool_calls"][0]["id"]==history[1]["tool_call_id"]=="native-context-read"
        receipt=json.loads(history[1]["content"])
        assert "blocks" not in receipt, "完整原文已有sources，不在回执重复"
        assert set(receipt["source_ids"])==known
        assert len(options["images"])==1 and data["attached_page_images"][0]["pdf_page"]==1
        return {"action":{"name":"report_structures","arguments":{"structures":[],"uncertainties":[],"reason":"只验证来源、图片和调用身份传递"}}}
    reader.extract_structure_candidates("",source=source,pdf_path=path,model=model,on_event=events.append)
    assert len(requests)==2
    receipt=next(e for e in events if e["status"]=="completed" and e.get("images_received"))
    assert receipt["original_context"]["request"]["observation"]["blocks"]
    assert all("block_id" in row and "bbox" in row for row in receipt["original_context"]["request"]["sources"])
    assert all(set(row)=={"source_id","pdf_page","content"} for row in requests[-1]["sources"])

def test_unregistered_tool_rows_are_not_removed(reader):
    request={"sources":[{"source_id":"known","content":"Verified original."}],
        "source_index":[{"source_id":"unread","preview":"Still available"}],
        "observation":{"blocks":[{"block_id":"unknown","text":"Must not lose this data"}]}}
    result,history=reader.compact_model_context(request,[])
    assert result["observation"]==request["observation"]
    assert result["source_index"]==request["source_index"]

def test_known_source_id_with_different_text_is_not_silently_dropped(reader):
    request={"sources":[{"source_id":"known","block_id":"block","pdf_page":1,"content":"Current original."}],
        "source_index":[],"observation":{"blocks":[{"block_id":"block","pdf_page":1,"text":"Different evidence.",
        "metadata":{"source_id":"known"}}]}}
    result,_=reader.compact_model_context(request,[])
    assert result["observation"]==request["observation"]

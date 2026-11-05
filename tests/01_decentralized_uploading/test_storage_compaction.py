"""#223：共享资料无损往返与发布后删除本机副本的故障边界。"""
import hashlib
import json
from copy import deepcopy
from types import SimpleNamespace
from pathlib import Path
import pytest
from sqlalchemy import select,func
from sqlalchemy.orm import Session
from backend import models
from backend.workdraft_models import ScientificSourceItem
from backend.ingest import field_sources
from backend.storage.files import LocalFileStorage


def test_repeated_contexts_share_one_payload_and_restore_every_field(sqlite_engine):
    with Session(sqlite_engine) as db:
        bundle=[{"quote":"Evidence "*900,"file_id":"main","page_start":1,"bbox":[0.1,2.3,4.5,6.7]}]
        original=[{"field":f"field{i}","current_value":i/10,"reason":"own reason",
                   "legacy_evidences":deepcopy(bundle)} for i in range(12)]
        packed=field_sources.compact_contexts(db,original)
        db.flush()
        assert db.scalar(select(func.count()).select_from(ScientificSourceItem))==1
        assert len(json.dumps(packed)) < len(json.dumps(original))/10
        assert field_sources.expand(db,packed)==original
        again=field_sources.compact_contexts(db,packed)
        assert again==packed
        assert db.scalar(select(func.count()).select_from(ScientificSourceItem))==1


def test_existing_fragment_refs_and_new_context_refs_expand_together(sqlite_engine):
    with Session(sqlite_engine) as db:
        quote={"quote":"Shared original text","file_id":"main"}
        db.add(ScientificSourceItem(id="a"*64,namespace="old",payload=quote));db.flush()
        original={"legacy_source_history":[{"evidences":[{"source_ref":"a"*64,"binding":{"scope":"150 GPa"}}],
                   "reason":"x"*5000}],"evidences":[{"source_ref":"a"*64,"binding":{}}]}
        packed=field_sources.compact_contexts(db,original)
        expanded=field_sources.expand(db,packed)
        assert expanded["legacy_source_history"][0]["evidences"][0]=={**quote,"scope":"150 GPa"}
        assert expanded["evidences"]==[quote]


def test_missing_and_cyclic_contexts_never_fall_back_to_current_data(sqlite_engine):
    with Session(sqlite_engine) as db:
        with pytest.raises(ValueError):
            field_sources.expand(db,{"shared_context_ref":"a"*64})
        db.add(ScientificSourceItem(id="b"*64,namespace="shared-context-v1",
            payload={"contract":"shared-context-v1","value":{"shared_context_ref":"b"*64}}))
        db.flush()
        with pytest.raises(ValueError,match="循环|cycle"):
            field_sources.expand(db,{"shared_context_ref":"b"*64})


@pytest.mark.parametrize("mode",["ok","missing","changed_remote","invalid_json","changed_local","wrong_identity"])
def test_local_artifact_removed_only_after_normal_verified_read(tmp_path,monkeypatch,mode):
    from backend.ingest import artifact_retention as retention, upload_tasks
    from backend.storage.paths import object_mode
    task="a"*32
    original={"task_id":task,"paper_id":1208,"paper_revision":1,"evidence":{"field":"valid"}}
    raw=json.dumps(original).encode()
    local=tmp_path/"local"/"result.json";local.parent.mkdir();local.write_bytes(raw)
    storage=LocalFileStorage(tmp_path/"objects")
    key=f"review_artifacts/{task}/submitted-1208-r1.json"
    import io
    if mode!="missing":
        content=raw
        if mode=="invalid_json":content=b'{"broken"';local.write_bytes(content)
        if mode=="wrong_identity":content=json.dumps({**original,"paper_id":999}).encode();local.write_bytes(content)
        if mode=="changed_remote":content=raw+b" "
        storage.put(key,io.BytesIO(content),"application/json")
    monkeypatch.setattr(retention,"create_storage",lambda:storage)
    monkeypatch.setattr(retention,"object_mode",lambda:True)
    def normal_read(*args,**kwargs):
        if mode=="changed_local":local.write_bytes(raw+b"new input")
        return storage.root/key
    monkeypatch.setattr(upload_tasks,"read_artifact_path",normal_read)
    result=retention.release_submitted_artifact(task,1208,1,local_path=local)
    assert result["deleted"]==(mode=="ok")
    assert local.exists()==(mode!="ok")


def test_new_snapshot_shares_structure_sources_and_closes_only_upload_body(sqlite_engine):
    from backend.services import manuscript_handoffs as h
    from backend import models
    with Session(sqlite_engine) as db:
        paper=models.Paper(title="Storage test",year=2026,uploaded_by_user_id=2,review_status="pending",
            upload_task_id="c"*32)
        db.add(paper);db.flush()
        work=models.ScientificWorkDraft(id="w",document_key="upload:"+"c"*32,target="upload",
            target_id="c"*32,owner_id=2,write_epoch="epoch",revision=3,body={"old":"x"*6000})
        db.add(work);db.flush()
        original_sources=[{"quote":"same immutable source "*400}]
        draft={"paper":{"title":"Storage test"},"material_states":[],"sources":original_sources}
        first=h.record_handoff(db,paper,SimpleNamespace(id=2,username="author",role="user"),
            action="submit",holder="review",initial=True,operation_id="first",
            draft=draft,records=[])
        db.flush()
        assert work.body=={} and work.document_key.startswith("closed:")
        stored=h.snapshot_event(db,paper.id,first["snapshot_id"]).classification_snapshot
        assert "shared_context_ref" in stored["manuscript_snapshot"]["draft"]["sources"]
        public=h.public_snapshot(db,paper,SimpleNamespace(id=2,role="user"),first["snapshot_id"])
        assert public["content"]["draft"]["sources"]==original_sources
        assert first["content_hash"]==h.content_hash(public["content"])


def test_failed_handoff_keeps_original_upload_body(sqlite_engine):
    from backend.services import manuscript_handoffs as h
    with Session(sqlite_engine) as db:
        paper=models.Paper(title="Rollback",year=2026,uploaded_by_user_id=2,review_status="pending",upload_task_id="d"*32)
        db.add(paper);db.flush()
        work=models.ScientificWorkDraft(id="w",document_key="upload:"+"d"*32,target="upload",
            target_id="d"*32,owner_id=2,write_epoch="epoch",revision=1,body={"keep":"current input"})
        db.add(work);db.commit()
        with pytest.raises(RuntimeError):
            with db.begin_nested():
                h.record_handoff(db,paper,SimpleNamespace(id=2,username="author",role="user"),
                    action="submit",holder="review",initial=True,operation_id="fail",
                    draft={"paper":{"title":"Rollback"},"material_states":[]},records=[])
                raise RuntimeError("fixed failure")
        assert work.body=={"keep":"current input"}
        assert work.document_key=="upload:"+"d"*32

"""#25：真实取消被后续阶段进度覆盖的回归。"""
from copy import deepcopy
from types import SimpleNamespace

import pytest

from backend.ingest.upload_contracts import apply_state_changes
from backend.ingest.upload_jobs import UploadCancelled


@pytest.mark.parametrize("target", ["reading", "summarizing", "ready", "extracting"])
def test_pending_cancel_cannot_be_overwritten_by_late_progress(target):
    state = {"status": "cancelling", "stage": "extracting", "cancel_requested_at": 10}
    with pytest.raises(UploadCancelled):
        apply_state_changes(state, now=20, status=target, stage=target)
    assert state["status"] == "cancelling"


def test_worker_dispatch_cooperatively_finishes_cancel_after_late_stage(tmp_path, monkeypatch):
    from backend.ingest import upload_jobs as jobs, upload_tasks
    from backend.rag import llm_context
    from backend.storage import paths
    source = tmp_path / "paper.md"; source.write_text("Results\nWe calculate electron phonon coupling and Tc.\n")
    task = "b" * 32
    state = dict(task_id=task,user_id=1,status="queued",parser_profile="legacy",file_kind="md",
        file_path=str(source),filename=source.name,
        files=[dict(file_id="main",role="main",kind="md",stored_path=str(source),original_filename=source.name)])
    monkeypatch.setattr(jobs,"get_state",lambda _:deepcopy(state))
    def update(_, **changes):
        state.update(apply_state_changes(state,now=20,**changes));return deepcopy(state)
    monkeypatch.setattr(jobs,"update_state",update)
    monkeypatch.setattr(jobs,"_original_path",lambda _:source)
    monkeypatch.setattr(jobs,"data_path",lambda name:tmp_path/name)
    monkeypatch.setattr(jobs,"markdown_path",lambda _:tmp_path/"parsed_markdown"/(task+".md"))
    (tmp_path/"artifacts").mkdir()
    monkeypatch.setattr(jobs,"artifact_directory",lambda _:tmp_path/"artifacts")
    monkeypatch.setattr(jobs,"_schedule_terminal_cleanup",lambda _:None)
    monkeypatch.setattr(upload_tasks,"available_published_path",lambda _,p:p)
    monkeypatch.setattr(paths,"object_mode",lambda:False)
    monkeypatch.setattr(llm_context,"get_llm_config",lambda:SimpleNamespace(model="fixture"))
    from backend.ingest import paper_first
    monkeypatch.setattr(paper_first, 'prepare_paper', lambda *_a, **_kw: {'paper': {}, 'material_states': []})
    def model(*_a,**_kw):
        return dict(paper_type="theoretical",theoretical_subtype="calculation",superconductor_kind="conventional",
            reason="本文计算电声耦合和Tc",source_ids=["review-source-0"],contribution_source_ids=["review-source-0"],tc_materials=[],paper={})
    monkeypatch.setattr(jobs,"complete_json",model)
    def specialized(_):
        update(task,status="cancelling",cancel_requested_at=19)
        return update(task,status="reading",stage="reading")  # 模拟结构读取晚返回。
    monkeypatch.setattr(jobs,"_process_conventional_upload_task",specialized)
    result=jobs._process_upload_task(task)
    assert result["status"]=="cancelled"

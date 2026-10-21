"""多文件主文判断先于昂贵的模型阅读。"""

import pytest

from backend.ingest.document_roles import assess_roles


def _file(file_id, name, role="attachment"):
    return {"file_id": file_id, "original_filename": name, "role": role, "kind": "pdf", "sha256": file_id}


MAIN = """## Predicted hot superconductivity in LaSc2H24 under pressure
10.1073/pnas.2401840121
Abstract
The authors study ternary superhydrides.
Introduction
Results and Discussion
"""
SI = """Supporting Information
Fig. S1. Ternary phase diagram.
Table S1. Calculated crystal structure.
Fig. S2. Further calculations.
"""


def test_si_first_and_manually_selected_as_main_is_corrected():
    files = [_file("si", "2024 La-Sc-H-SI.pdf", "main"), _file("article", "2024 La-Sc-H.pdf")]
    result = assess_roles(files, {"si": SI, "article": MAIN})
    assert result["status"] == "resolved"
    assert result["main_file_id"] == "article"
    assert [item["effective_role"] for item in result["files"]] == ["supplementary", "main"]
    assert result["files"][0]["declared_role"] == "main"


def test_article_first_stays_main():
    result = assess_roles([_file("article", "paper.pdf", "main"), _file("si", "paper-supplementary.pdf")],
                          {"article": MAIN, "si": SI})
    assert result["status"] == "resolved"
    assert result["main_file_id"] == "article"


def test_two_articles_or_unreadable_text_wait_for_user():
    files = [_file("a", "one.pdf", "main"), _file("b", "two.pdf")]
    assert assess_roles(files, {"a": MAIN, "b": MAIN})["status"] == "needs_review"
    assert assess_roles(files, {"a": "scan unreadable", "b": SI})["status"] == "needs_review"
    assert assess_roles([_file("si", "paper-SI.pdf", "main")], {"si": SI})["status"] == "needs_review"
    assert assess_roles([_file("weak", "paper.pdf", "main")], {"weak": "scan unreadable"})["status"] == "needs_review"


def test_plain_text_journal_title_and_byline_identify_experimental_article():
    text = ("Novel Cooperative Interactions and Structural Ordering in H2S-H2\n"
            "Timothy A. Strobel, P. Ganesh, and Russell J. Hemley\n"
            "Geophysical Laboratory, Carnegie Institution of Washington\n"
            "DOI: 10.1103/PhysRevLett.107.255503\n")
    result = assess_roles([_file("article", "2011 H2S-H2.pdf", "attachment")], {"article": text})
    assert result["status"] == "resolved"
    assert result["files"][0]["effective_role"] == "main"


def test_all_text_generators_share_effective_main_and_si(tmp_path):
    from backend.ingest.upload_source_bundle import task_source_chunks, text_sources

    task_id = "d" * 32
    root = tmp_path / task_id
    root.mkdir()
    files = []
    for file_id, role, content in (("main", "main", MAIN), ("si", "supplementary", SI),
                                   ("other", "attachment", "Unrelated paper content")):
        (root / f"{file_id}.md").write_text(content, encoding="utf-8")
        files.append({"file_id": file_id, "kind": "pdf", "role": role,
                      "original_filename": f"{file_id}.pdf"})
    state = {"files": files}
    assert [item["file_id"] for item in text_sources(task_id, state, tmp_path)] == ["main", "si"]
    chunks = task_source_chunks(task_id, state, tmp_path)
    assert {item["file_id"] for item in chunks} == {"main", "si"}
    assert {item["file_role"] for item in chunks if item["file_id"] == "main"} == {"main"}


def test_worker_pauses_ambiguous_bundle_before_any_chunk_model_call(tmp_path, monkeypatch):
    from backend.ingest import upload_jobs

    task_id = "b" * 32
    files = []
    for file_id in ("a", "b"):
        path = tmp_path / f"{file_id}.pdf"
        path.write_text("test", encoding="utf-8")
        files.append({**_file(file_id, f"{file_id}.pdf"), "stored_path": str(path),
                      "kind": "pdf", "upload_status": "completed"})
    state = {"task_id": task_id, "user_id": 7, "status": "queued", "stage": "queued",
             "parser_profile": "legacy", "files": files}
    monkeypatch.setattr(upload_jobs, "get_state", lambda _: state)
    monkeypatch.setattr(upload_jobs, "markdown_path", lambda _: tmp_path / f"{task_id}.md")
    monkeypatch.setattr(upload_jobs, "artifact_directory", lambda _: tmp_path / "artifacts")
    monkeypatch.setattr(upload_jobs, "data_path", lambda name: tmp_path / name)
    monkeypatch.setattr(upload_jobs, "extract_structure_candidates", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(upload_jobs, "_extract_markdown", lambda file_state, source: MAIN.replace("LaSc2H24", source.stem))
    monkeypatch.setattr(upload_jobs, "_read_chunk", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("不能调用模型")))
    monkeypatch.setattr(upload_jobs, "schedule_cleanup", lambda _: None)

    def update(_, **changes):
        state.update(changes)
        return dict(state)

    monkeypatch.setattr(upload_jobs, "update_state", update)
    paused = upload_jobs._process_upload_task(task_id)
    assert paused["status"] == "needs_role_review"
    assert paused["role_assessment"]["main_file_id"] is None


def test_confirmed_roles_reuse_cached_text_with_nonlegacy_profile(tmp_path, monkeypatch):
    from backend.ingest import upload_jobs

    task_id = "c" * 32
    files = []
    cached = {"a": MAIN, "b": SI}
    root = tmp_path / "parsed_markdown" / task_id
    root.mkdir(parents=True)
    for file_id, content in cached.items():
        source = tmp_path / f"{file_id}.txt"
        source.write_text("original source", encoding="utf-8")
        (root / f"{file_id}.md").write_text(content, encoding="utf-8")
        files.append({**_file(file_id, f"{file_id}.txt", "main" if file_id == "a" else "supplementary"),
                      "kind": "txt", "stored_path": str(source), "upload_status": "completed"})
    assessment = assess_roles(files, cached)
    assessment["status"] = "user_confirmed"
    state = {"task_id": task_id, "user_id": 7, "status": "queued", "stage": "queued",
             "parser_profile": "layout", "files": files, "file_path": files[0]["stored_path"],
             "role_assessment": assessment}
    monkeypatch.setattr(upload_jobs, "get_state", lambda _: state)
    monkeypatch.setattr(upload_jobs, "markdown_path", lambda _: tmp_path / f"{task_id}.md")
    monkeypatch.setattr(upload_jobs, "artifact_directory", lambda _: tmp_path / "artifacts")
    monkeypatch.setattr(upload_jobs, "data_path", lambda name: tmp_path / name)
    monkeypatch.setattr(upload_jobs, "extract_structure_candidates", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(upload_jobs, "_extract_markdown", lambda *_args: (_ for _ in ()).throw(AssertionError("不应重新提取")))
    monkeypatch.setattr(upload_jobs, "_read_chunk", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("reached_chunk_model")))

    def update(_, **changes):
        state.update(changes)
        return dict(state)

    monkeypatch.setattr(upload_jobs, "update_state", update)
    with pytest.raises(RuntimeError, match="reached_chunk_model"):
        upload_jobs._process_upload_task(task_id)
    assert state["role_assessment"]["status"] == "user_confirmed"

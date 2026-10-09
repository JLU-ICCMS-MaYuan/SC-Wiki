"""人工证据与论文原文分离，并绑定实际修改的字段版本。"""

from io import BytesIO
from types import SimpleNamespace

import pytest
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.ingest import manual_evidence as manual
from backend.manual_evidence_models import ScientificManualEvidence
from backend.models import PaperHistoryEvent


def snapshot(value_hash="new", source_hash="source"):
    return {"target": "upload", "target_id": "task", "records": [{
        "key": "field", "item_key": "stable-field", "field": "paper.authors",
        "content_hash": value_hash, "source_hash": source_hash, "current_value": value_hash,
    }]}


def test_legacy_form_normalization_is_not_a_human_edit():
    previous = snapshot("old")
    current = snapshot("new")
    previous["records"][0].update(kind="property", current_value={
        "record": {"value_kind": "range", "value_raw": "155 K to 166 K", "value_min": 155, "value_max": 166},
        "state": {"calculation_context": {"mu_star": 0.1}},
    })
    current["records"][0].update(kind="property", current_value={
        "record": {"value_kind": "range", "value_raw": "155–166", "value_min": 155, "value_max": 166},
        "state": {"calculation_context": None},
    })
    assert manual.changed_records(current, previous) == []


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    ScientificManualEvidence.__table__.create(engine)
    with Session(engine) as db:
        yield db
    engine.dispose()


def test_reason_is_required_even_with_text_evidence(session):
    before, current = snapshot("old"), snapshot()
    assert manual.validate_submission(session, current, before)[0]["code"] == "manual_reason_required"
    manual.save_explanation(session, current, before, "stable-field", 7, reason="",
                            no_evidence_reason="", text_items=[{"text": "实验记录", "source_description": "实验室笔记"}])
    assert manual.validate_submission(session, current, before)[0]["code"] == "manual_reason_required"
    saved = manual.save_explanation(session, current, before, "stable-field", 7,
                                    reason="对照实验记录判断", no_evidence_reason="", text_items=[{"text": "实验记录", "source_description": "实验室笔记"}])
    assert saved["items"][0]["kind"] == "text"
    assert manual.validate_submission(session, current, before) == []
    prepared = manual.current_ids(session, current, before)["field"]
    assert prepared == {"id": saved["id"], "version": saved["evidence_version"]}
    changed = manual.save_explanation(session, current, before, "stable-field", 7,
        reason="补充核验", no_evidence_reason="", text_items=[{"text": "实验记录", "source_description": "实验室笔记"}])
    assert changed["evidence_version"] > prepared["version"]


def test_no_evidence_needs_separate_absence_reason_and_reverting_needs_no_explanation(session):
    before, current = snapshot("old"), snapshot()
    manual.save_explanation(session, current, before, "stable-field", 7,
                            reason="依据专业判断", no_evidence_reason="", text_items=[])
    assert manual.validate_submission(session, current, before)[0]["code"] == "manual_evidence_absence_reason_required"
    manual.save_explanation(session, current, before, "stable-field", 7,
                            reason="依据专业判断", no_evidence_reason="原始实验记录已遗失", text_items=[])
    assert manual.validate_submission(session, current, before) == []
    assert manual.validate_submission(session, before, before) == []


def test_transfer_rechecks_explanation_after_preflight(session):
    before, current = snapshot("old"), snapshot()
    manual.save_explanation(session, current, before, "stable-field", 7,
                            reason="人工核验", no_evidence_reason="无可共享文件", text_items=[])
    assert manual.validate_submission(session, current, before) == []
    manual.save_explanation(session, current, before, "stable-field", 7,
                            reason="", no_evidence_reason="", text_items=[])
    with pytest.raises(manual.ManualEvidenceError) as stale:
        manual.transfer_to_paper(session, current, before, 29, 1)
    assert stale.value.code == "manual_evidence_incomplete"
    assert session.query(ScientificManualEvidence).one().target == "upload"


def test_image_is_private_and_retained_after_transfer(session, tmp_path, monkeypatch):
    monkeypatch.setattr(manual, "settings", SimpleNamespace(sc_wiki_data_dir=tmp_path))
    before, current = snapshot("old"), snapshot()
    manual.save_explanation(session, current, before, "stable-field", 7,
                            reason="图示给出对应结构", no_evidence_reason="", text_items=[])
    image = BytesIO()
    Image.new("RGB", (4, 4), "white").save(image, format="PNG")
    saved = manual.add_file(session, current, before, "stable-field", 7,
                            filename="page.png", raw=image.getvalue(), source_description="论文 PDF 截图")
    item = saved["items"][0]
    assert item["kind"] == "image"
    assert "storage_key" not in item
    assert manual.validate_submission(session, current, before) == []
    assert manual.file_path(saved["id"], item["id"]).read_bytes() == image.getvalue()
    persisted = {**snapshot(source_hash="paper-source"), "target": "paper", "target_id": "29",
                 "review_state": ["pending", None, 2]}
    manual.transfer_to_paper(session, current, before, 29, 2, persisted)
    row = session.get(ScientificManualEvidence, saved["id"])
    assert (row.target, row.paper_id, row.paper_revision, row.status) == ("paper", 29, 2, "submitted")
    assert row.source_hash == "paper-source"
    context = manual.review_context(session, persisted)["field"]
    assert context["items"][0]["source_description"] == "论文 PDF 截图"
    assert context["images"][0]["data_url"].startswith("data:image/png;base64,")
    manual.mark_ai_read(session, context["images"], read=True)
    assert session.get(ScientificManualEvidence, saved["id"]).items[0]["ai_read_status"] == "read"
    assert manual.cleanup_unsubmitted(session, "task") == []
    assert manual.file_path(saved["id"], item["id"]).is_file()


def test_reviewer_reason_does_not_overwrite_uploader_evidence(session):
    before, current = snapshot("old"), snapshot()
    uploader = manual.save_explanation(session, current, before, "stable-field", 7,
        reason="上传者判断", no_evidence_reason="", text_items=[{"text": "原始记录", "source_description": "实验日志"}], actor_name="author")
    paper = {**current, "target": "paper", "target_id": "29", "review_state": ["pending", None, 1]}
    manual.transfer_to_paper(session, current, before, 29, 1, paper)
    reviewer = manual.save_explanation(session, paper, before, "stable-field", 8,
        reason="审核员复核", no_evidence_reason="未补充新文件", text_items=[], actor_name="reviewer")
    assert reviewer["id"] != uploader["id"]
    found = manual.read_field(session, paper, before, "stable-field")
    assert found["reason"] == "审核员复核"
    assert found["history"][0]["items"][0]["text"] == "原始记录"
    assert found["history"][0]["actor_name"] == "author"
    context = manual.review_context(session, paper)["field"]
    assert {item["submitted_by_user_id"] for item in context["items"]} == {7}
    assert {decision["submitted_by_user_id"] for decision in context["decisions"]} == {7, 8}
    assert context["items"][0]["content"] == "原始记录"


def test_previous_revision_evidence_remains_visible_as_history(session, tmp_path, monkeypatch):
    monkeypatch.setattr(manual, "settings", SimpleNamespace(sc_wiki_data_dir=tmp_path))
    before, current = snapshot("old"), snapshot()
    manual.save_explanation(session, current, before, "stable-field", 7,
                            reason="按实验记录修正", no_evidence_reason="", text_items=[])
    saved = manual.add_file(session, current, before, "stable-field", 7,
                            filename="note.txt", raw=b"source", source_description="实验记录")
    paper = {**current, "target": "paper", "target_id": "29", "review_state": ["pending", None, 1]}
    manual.transfer_to_paper(session, current, before, 29, 1, paper)
    next_revision = {**paper, "review_state": ["pending", None, 2]}
    found = manual.read_field(session, next_revision, before, "stable-field")
    assert found["history"][0]["id"] == saved["id"]
    _, entry, path = manual.file_entry(session, next_revision, "stable-field", saved["items"][0]["id"])
    assert entry["filename"] == "note.txt"
    assert path.read_bytes() == b"source"


def test_spoofed_image_and_stale_version_are_rejected(session):
    before, current = snapshot("old"), snapshot()
    with pytest.raises(manual.ManualEvidenceError, match="有效图片"):
        manual.add_file(session, current, before, "stable-field", 7,
                        filename="fake.png", raw=b"not an image", source_description="截图")
    manual.save_explanation(session, current, before, "stable-field", 7,
                            reason="依据原文", no_evidence_reason="没有可分享的截图", text_items=[])
    assert manual.validate_submission(session, snapshot("changed-again"), before)[0]["code"] == "manual_reason_required"
    mismatched_paper = {**snapshot("different"), "target": "paper", "target_id": "29"}
    with pytest.raises(manual.ManualEvidenceError, match="正式字段已变化"):
        manual.transfer_to_paper(session, current, before, 29, 2, mismatched_paper)


def test_file_limits_and_checksum_protect_private_preview(session, tmp_path, monkeypatch):
    monkeypatch.setattr(manual, "settings", SimpleNamespace(sc_wiki_data_dir=tmp_path))
    before, current = snapshot("old"), snapshot()
    with pytest.raises(manual.ManualEvidenceError) as too_large:
        manual.add_file(session, current, before, "stable-field", 7,
                        filename="large.txt", raw=b"x" * (manual.MAX_FILE_BYTES + 1), source_description="实验记录")
    assert too_large.value.code == "manual_file_size"
    with pytest.raises(manual.ManualEvidenceError) as wrong_type:
        manual.add_file(session, current, before, "stable-field", 7,
                        filename="page.png", raw=b"plain text", source_description="实验记录")
    assert wrong_type.value.code == "manual_file_invalid"
    for index in range(manual.MAX_ITEMS):
        saved = manual.add_file(session, current, before, "stable-field", 7,
                                filename=f"note-{index}.txt", raw=b"source", source_description="实验记录")
    with pytest.raises(manual.ManualEvidenceError) as too_many:
        manual.add_file(session, current, before, "stable-field", 7,
                        filename="extra.txt", raw=b"source", source_description="实验记录")
    assert too_many.value.code == "manual_evidence_limit"
    item = saved["items"][0]
    manual.file_path(saved["id"], item["id"]).write_bytes(b"tampered")
    with pytest.raises(manual.ManualEvidenceError) as tampered:
        manual.file_entry(session, current, "stable-field", item["id"])
    assert tampered.value.code == "manual_file_unavailable"


def test_review_images_have_batch_wide_indexes_and_bounded_payload(session, tmp_path, monkeypatch):
    monkeypatch.setattr(manual, "settings", SimpleNamespace(sc_wiki_data_dir=tmp_path))
    image = BytesIO()
    Image.new("RGB", (4, 4), "white").save(image, format="PNG")
    raw = image.getvalue()
    before, current = snapshot("old"), snapshot()
    previous_second = {**before["records"][0], "key": "second", "item_key": "second-field"}
    current_second = {**current["records"][0], "key": "second", "item_key": "second-field"}
    before["records"].append(previous_second)
    current["records"].append(current_second)
    for item_key in ("stable-field", "second-field"):
        manual.add_file(session, current, before, item_key, 7,
                        filename="page.png", raw=raw, source_description="人工截图")
    context = manual.review_context(session, current)
    assert [context[key]["items"][0]["image_index"] for key in ("field", "second")] == [1, 2]
    monkeypatch.setattr(manual, "MAX_REVIEW_IMAGE_BYTES", len(raw))
    limited = manual.review_context(session, current)
    assert len(limited["field"]["images"]) == 1
    assert limited["second"]["images"] == []
    assert limited["second"]["items"][0]["read_status"] == "not_read"


def test_unsubmitted_cleanup_removes_only_its_private_files(session, tmp_path, monkeypatch):
    monkeypatch.setattr(manual, "settings", SimpleNamespace(sc_wiki_data_dir=tmp_path))
    before, current = snapshot("old"), snapshot()
    saved = manual.add_file(session, current, before, "stable-field", 7,
                            filename="note.txt", raw=b"manual evidence", source_description="lab note")
    path = manual.file_path(saved["id"], saved["items"][0]["id"])
    roots = manual.cleanup_unsubmitted(session, "task")
    manual.remove_file_roots(roots)
    assert not path.exists()
    assert session.get(ScientificManualEvidence, saved["id"]) is None


def test_paper_baseline_uses_first_value_and_revert_needs_no_reason(session):
    from backend.ingest import property_evidence as evidence, scientific_evidence as science
    PaperHistoryEvent.__table__.create(session.get_bind())
    session.add(PaperHistoryEvent(paper_id=29, paper_revision=1, event_type="modified",
                                  classification_snapshot={"manual_edit_baseline": {"title": "Original"}}))
    session.add(PaperHistoryEvent(paper_id=29, paper_revision=1, event_type="modified",
                                  classification_snapshot={"manual_edit_baseline": {"title": "Changed"}}))
    session.flush()
    old = science.field_records("paper", "paper", {"title": "Original"}, science.PAPER_FIELDS)[0]
    old_hash = evidence.digest(science.canonical(old["claim"]))
    current = {"target": "paper", "target_id": "29", "review_state": ["pending", None, 1],
               "records": [{"key": old["key"], "item_key": old["item_key"], "field": "paper.title",
                            "content_hash": old_hash, "source_hash": "source", "current_value": "Original"}]}
    baseline = manual.paper_baseline(session, current)
    assert manual.validate_submission(session, current, baseline) == []
    current["records"][0]["content_hash"] = "changed-hash"
    current["records"][0]["current_value"] = "Changed"
    assert manual.validate_submission(session, current, baseline)[0]["code"] == "manual_reason_required"


def test_review_ai_receives_image_separately_from_paper_sources(monkeypatch):
    from backend.ingest import property_evidence as evidence
    from backend.rag import llm

    calls = []
    def complete(_, prompt, **kwargs):
        calls.append((prompt, kwargs))
        return {"results": [{"key": "field", "status": "supported", "reason": "人工图片仅作参考", "evidences": []}]}
    monkeypatch.setattr(llm, "complete_json", complete)
    record = {"key": "field", "field": "paper.title", "claim": {"value": "H3S"},
              "editable_fields": [], "evidences": []}
    context = {"field": {"reason": "参考截图", "items": [{"kind": "image", "source_description": "手工截图"}],
                         "images": [{"row_id": "r", "item_id": "i", "data_url": "data:image/png;base64,AA=="}]}}
    read = []
    result = evidence.evaluate_batch([record], [], "review_all", human_context=context, image_read_out=read)
    assert calls[0][1]["images"] == ["data:image/png;base64,AA=="]
    assert 'human_provided_evidence' in calls[0][0]
    assert result[0]["status"] == "missing"  # 人工图片不能伪装成论文原文引句。
    assert read[0][1] is True


def test_unsupported_vision_model_records_image_not_read(monkeypatch):
    import httpx
    from openai import BadRequestError
    from backend.ingest import property_evidence as evidence
    from backend.rag import llm

    calls = []
    def complete(_, prompt, **kwargs):
        calls.append(kwargs)
        if kwargs.get("images"):
            response = httpx.Response(400, request=httpx.Request("POST", "https://example.test/chat"))
            raise BadRequestError("images unsupported", response=response, body=None)
        return {"results": [{"key": "field", "status": "missing", "reason": "无论文来源", "evidences": []}]}
    monkeypatch.setattr(llm, "complete_json", complete)
    record = {"key": "field", "field": "paper.title", "claim": {"value": "H3S"},
              "editable_fields": [], "evidences": []}
    context = {"field": {"reason": "参考截图", "items": [],
                         "images": [{"row_id": "r", "item_id": "i", "data_url": "data:image/png;base64,AA=="}]}}
    read = []
    evidence.evaluate_batch([record], [], "review_all", human_context=context, image_read_out=read)
    assert len(calls) == 2
    assert "images" not in calls[1]
    assert read[0][1] is False

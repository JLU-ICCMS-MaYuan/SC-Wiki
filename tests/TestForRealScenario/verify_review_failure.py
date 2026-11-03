"""核对结束必须保留技术失败原由，不能统一改写为依赖变化。"""
from copy import deepcopy


def test_review_draft_retains_actual_technical_error(monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", "isolated-review-failure-test-key")
    from backend.ingest import model_review
    from backend.ingest.property_evidence import digest

    original = model_review.review_fields
    calls = []
    def unavailable(*args, **kwargs):
        calls.append(True)
        raise TimeoutError("isolated provider timeout")
    def review(records, chunks, **kwargs):
        return original(records, chunks, model=unavailable, **kwargs)
    monkeypatch.setattr(model_review, "review_fields", review)

    def rebuild(draft):
        return {"records": [{"key": "title", "item_key": "title", "field": "paper.title",
            "current_value": draft["paper"]["title"], "content_hash": digest(draft["paper"]["title"]),
            "source_hash": "source", "state_review_context": None, "required": True}],
            "chunks": [{"file_id": "main", "content": "Reported paper title."}]}
    draft = {"paper": {"title": "Reported paper title."}, "material_states": []}
    before = deepcopy(draft)
    current, snapshot, results, report = model_review.review_draft(draft, rebuild, model_name="isolated")
    assert draft == before and current["paper"]["title"] == before["paper"]["title"]
    assert len(calls) == 1
    assert results["title"]["status"] == "unchecked"
    assert results["title"]["review_error"] == "TimeoutError"
    assert "TimeoutError" in results["title"]["reason"]
    assert results["title"]["human_confirmed"] is False
    assert report["unfinished_fields"] == 1 and report["completed_fields"] == 0

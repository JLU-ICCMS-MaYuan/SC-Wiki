"""真实内存 Qdrant 边界验证重建保留源数据、失败不切换及查询路由。"""

import json
import asyncio

import pytest
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from scripts.embedding.rebuild_collection import rebuild, records, fingerprint


def source_client():
    client = QdrantClient(":memory:")
    client.create_collection("paper_chunks", vectors_config=VectorParams(size=2, distance=Distance.COSINE))
    client.upsert("paper_chunks", points=[
        PointStruct(id=i, vector=[1.0, 0.0], payload={
            "document": f"论文片段 {i}", "paper_id": str(i),
            "paper_revision": 3, "source_kind": "scientific", "attribution": {"value": 0, "unit": "K"},
        }) for i in [1, 2, 3]
    ])
    return client


def test_rebuild_retains_every_source_point_and_payload(tmp_path):
    client = source_client()
    before = list(records(client, "paper_chunks"))
    receipt = rebuild(client, "paper_chunks", "qwen_new", lambda texts: [[0.0, 1.0]] * len(texts),
                      tmp_path / "backup", dimensions=2, batch_size=2)
    assert receipt["passed"] and receipt["points"] == 3
    assert fingerprint(list(records(client, "paper_chunks"))) == fingerprint(before)
    target = list(records(client, "qwen_new"))
    assert {p.id: p.payload for p in target} == {p.id: p.payload for p in before}
    assert all(p.vector == [0.0, 1.0] for p in target)
    assert len((tmp_path / "backup/source.jsonl").read_text().splitlines()) == 3
    assert json.loads((tmp_path / "backup/receipt.json").read_text())["source_unchanged"]


def test_failed_batch_keeps_original_and_no_success_receipt(tmp_path):
    client = source_client()
    before = fingerprint(list(records(client, "paper_chunks")))
    calls = []

    def failing_embed(texts):
        calls.append(texts)
        if len(calls) > 1:
            raise RuntimeError("upstream unavailable")
        return [[0.0, 1.0]] * len(texts)

    with pytest.raises(RuntimeError, match="upstream unavailable"):
        rebuild(client, "paper_chunks", "qwen_partial", failing_embed,
                tmp_path / "backup", dimensions=2, batch_size=2)
    assert fingerprint(list(records(client, "paper_chunks"))) == before
    assert not (tmp_path / "backup/receipt.json").exists()
    assert (tmp_path / "backup/source.jsonl").exists()
    with pytest.raises(ValueError, match="独立集合"):
        rebuild(client, "paper_chunks", "paper_chunks", failing_embed,
                tmp_path / "other", dimensions=2)


def test_logical_primary_collection_uses_new_model_space(monkeypatch):
    from backend.rag import vectordb
    from backend.rag.search import vector_search

    seen = []
    monkeypatch.setattr(vectordb, "COLLECTION_NAME", "qwen_new")
    monkeypatch.setattr(vector_search, "embed_texts", lambda texts, **kwargs: seen.append(kwargs) or [[1.0, 0.0]])
    monkeypatch.setattr(vector_search, "qdrant_search", lambda vector, **kwargs: seen.append(kwargs) or [])
    asyncio.run(vector_search.search_by_semantics("query", collection="paper_chunks"))
    assert seen[0] == {"purpose": "query"}
    assert seen[1]["collection"] == "qwen_new"
    asyncio.run(vector_search.search_by_semantics("query", collection="review_chunks"))
    assert seen[3]["collection"] == "review_chunks"

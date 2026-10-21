"""
embedder.py — 文本向量化和索引模块。

将文本块转为向量，存入 Qdrant。

Embedding 方案：
- 使用独立 Embedding 配置调用 OpenAI 兼容接口
- 如果未配置，抛出明确的错误提示
"""

from __future__ import annotations

from math import isfinite

from openai import OpenAI, OpenAIError

from backend.rag.config import settings
from backend.rag.vectordb import add_chunks


def embed_texts(texts: list[str]) -> list[list[float]]:
    """将文本列表批量向量化。

    Args:
        texts: 文本列表

    Returns:
        向量列表，shape (n_texts, dim)
    """
    if not texts:
        return []
    if not settings.embedding_key:
        raise RuntimeError(
            "Embedding API key 未配置。请设置 EMBEDDING_API_KEY 或 OPENAI_API_KEY。\n"
            "  在 .env 中添加: EMBEDDING_API_KEY=sk-..."
        )

    embeddings: list[list[float]] = []
    expected_dim = settings.embedding_dimensions
    options = {"dimensions": expected_dim} if expected_dim is not None else {}
    try:
        with OpenAI(
            api_key=settings.embedding_key,
            base_url=settings.embedding_url,
            timeout=30,
            max_retries=1,
        ) as client:
            for start in range(0, len(texts), settings.embedding_batch_size):
                batch = texts[start:start + settings.embedding_batch_size]
                resp = client.embeddings.create(
                    model=settings.embedding_model, input=batch,
                    encoding_format="float", **options,
                )
                # 上游可能改变返回顺序，必须按 index 与原文对应。
                if not isinstance(resp.data, list) or len(resp.data) != len(batch):
                    raise RuntimeError("Embedding 响应数量与输入不一致")
                if any(type(item.index) is not int for item in resp.data):
                    raise RuntimeError("Embedding 响应索引无效")
                items = sorted(resp.data, key=lambda item: item.index)
                if [item.index for item in items] != list(range(len(batch))):
                    raise RuntimeError("Embedding 响应索引与输入不一致")
                for item in items:
                    vector = item.embedding
                    if not isinstance(vector, list) or not vector or any(
                        not isinstance(value, (int, float)) or not isfinite(value)
                        for value in vector
                    ):
                        raise RuntimeError("Embedding 响应向量无效")
                    if expected_dim is None:
                        expected_dim = len(vector)
                    if len(vector) != expected_dim:
                        raise RuntimeError("Embedding 响应维度与配置或其他向量不一致")
                    embeddings.append(vector)
    except OpenAIError:
        # 不向日志或上层响应传播供应商可能包含凭据的原始错误。
        raise RuntimeError("Embedding 服务调用失败，请检查配置、额度或网络") from None
    return embeddings


def index_chunks(
    chunk_data: list[dict],
    embeddings: list[list[float]],
) -> list[str]:
    """将 chunks 索引到 Qdrant。

    Args:
        chunk_data: [{"id": str, "paper_id": int, "chunk_index": int,
                       "section_name": str, "content": str}, ...]
        embeddings: 对应的向量列表

    Returns:
        成功索引的 chunk id 列表
    """
    ids = add_chunks(chunk_data, embeddings)
    return ids


def embed_and_index_chunks(chunk_data: list[dict]) -> int:
    if not chunk_data:
        return 0
    embeddings = embed_texts([item["content"] for item in chunk_data])
    return len(index_chunks(chunk_data, embeddings))


def chunk_and_embed(markdown_text: str, paper_id: int) -> int:
    """论文全文 → 语义分块 → 向量化 → Qdrant。返回索引的 chunk 数。"""
    from backend.ingest.chunker import chunk_paper

    chunks = chunk_paper(markdown_text, paper_id)
    if not chunks:
        print(f"  [RAG] paper_id={paper_id}: 无有效文本块，跳过向量化")
        return 0

    chunk_dicts = [
        {"id": f"paper_{paper_id}_chunk_{c.chunk_index}",
         "paper_id": c.paper_id, "chunk_index": c.chunk_index,
         "section_name": c.section_name or "", "content": c.content}
        for c in chunks
    ]
    texts = [c.content for c in chunks]
    embeddings = embed_texts(texts)
    ids = index_chunks(chunk_dicts, embeddings)
    print(f"  [RAG] paper_id={paper_id}: {len(ids)} chunks 已索引")
    return len(ids)

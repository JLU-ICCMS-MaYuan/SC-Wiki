"""
reranker.py — RCS（Re-ranking and Contextual Summarization）重排序模块。

对检索到的 chunks，让 LLM 逐个打分，过滤低分噪声。
这是 PaperQA2 的核心方法。
"""

from __future__ import annotations

import json
from typing import Any
from openai import APIStatusError

from backend.rag.llm_client import get_llm_client
from backend.rag.llm_context import UserCredentialError, get_llm_config
from backend.rag.core.prompts import RERANK_SYSTEM_PROMPT


async def rerank_chunks(
    query: str,
    chunks: list[dict],
    top_k: int = 5,
    min_score: int = 3,
) -> list[dict]:
    """对检索结果进行 LLM 评分和过滤。

    Args:
        query: 用户问题
        chunks: 检索到的 chunks
        top_k: 最多保留多少条
        min_score: 最低保留分数（0-5）

    Returns:
        过滤和排序后的 chunks（score 从高到低）
    """
    if not chunks:
        return []

    if not get_llm_config().api_key:
        # 没有 API key 时，全部保留（不评分）
        return chunks[:top_k]

    # 构造评分 prompt
    chunks_text = ""
    for i, ch in enumerate(chunks):
        chunks_text += f"\n[{i}] paper_id={ch.get('paper_id')} | {ch.get('content', '')[:300]}...\n"

    user_prompt = f"""用户问题: {query}

文献片段:
{chunks_text}

请对每个片段的相关性评分。"""

    client = get_llm_client()

    try:
        resp = client.chat.completions.create(
            model=get_llm_config().model,
            messages=[
                {"role": "system", "content": RERANK_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
        )

        result = json.loads(resp.choices[0].message.content)
        scores = result.get("scores", [])

        # 按评分过滤和排序
        scored_chunks = []
        for item in scores:
            idx = item.get("index")
            score = item.get("score", 0)
            if 0 <= idx < len(chunks) and score >= min_score:
                chunk = dict(chunks[idx])
                chunk["relevance_score"] = score
                chunk["relevance_reason"] = item.get("reason", "")
                scored_chunks.append(chunk)

        # 按分数降序排列
        scored_chunks.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)

        result["answerable"] = result.get("answerable", False)
        result["brief_reason"] = result.get("brief_reason", "")

        return scored_chunks[:top_k]

    except UserCredentialError:
        raise
    except Exception as e:
        if isinstance(e, APIStatusError) and e.status_code in {401, 403} and get_llm_config().user_supplied:
            # 不携带可能包含密钥的上游异常链，也不改用服务端凭据重试。
            raise UserCredentialError(
                "你配置的 AI 供应商认证失败，请检查 API Key 和权限，或在顶栏切回默认模型。"
            ) from None
        # 评分失败时，保留原始结果
        print("    [Rerank] 评分失败，保留原始顺序")
        return chunks[:top_k]

"""Stable service facade for SC-Wiki internal RAG APIs."""

from __future__ import annotations

import asyncio
import concurrent.futures
import contextvars
import json
import re
from pathlib import Path
from typing import Any, AsyncIterator

from sqlalchemy import desc, func, select
from sqlalchemy.orm import joinedload

from backend.rag.config import get_rag_settings
from backend.rag.llm_context import UserCredentialError, get_llm_config
from backend.rag.llm_client import get_llm_client


class RagDataUnavailableError(RuntimeError):
    """Raised when the RAG database or Qdrant data is unavailable."""


class RagChatUnavailableError(RuntimeError):
    """Raised when LLM-backed chat is not configured."""


class RagInternalError(RuntimeError):
    """Raised when the internal RAG runtime fails unexpectedly."""


class RagNotFoundError(RuntimeError):
    """Raised when a requested RAG resource does not exist."""


QUESTION_MAX_LENGTH = 1000
POLISH_MAX_TOKENS = 4096
_POLISH_TEMPLATE = Path(__file__).with_name("prompts") / "prompt_polish.md"
# ASCII 边界允许识别紧邻中文的科学表达；不把 200 误认为 1200 中的子串。
_SCIENTIFIC_TOKEN = re.compile(
    r"\{\{[^{}]+\}\}|\[PID_\d+\]|10\.\d{4,9}/[^\s，。；;]+|"
    r"(?<![A-Za-z0-9_])(?:"
    r"(?:[A-Z][a-z]?[0-9₀-₉]*){2,}|[A-Z][a-z]?[0-9₀-₉]+|"
    r"[+−-]?\d+(?:\.\d+)?(?:[eE][+−-]?\d+)?(?:[–−-]\d+(?:\.\d+)?)?|"
    r"Tc(?:\([A-Za-z]+\))?|DOI|[GMk]?Pa|meV|eV|K|°C|"
    r"[α-ωΑ-Ω](?:_[A-Za-z]+)?\*?"
    r")(?![A-Za-z0-9_])"
)


def validate_polish_response(original: str, response: Any) -> str:
    """拒绝不完整或丢失可确定原文信息的结果；语义质量另由真实评测验证。"""
    choices = getattr(response, "choices", None)
    if not choices or getattr(choices[0], "finish_reason", None) != "stop":
        raise ValueError("润色结果不完整")
    message = getattr(choices[0], "message", None)
    content = getattr(message, "content", None)
    if (not isinstance(content, str) or getattr(message, "refusal", None)
            or getattr(message, "tool_calls", None) or getattr(message, "function_call", None)):
        raise ValueError("润色结果无效")
    suggestion = content.strip()
    if not suggestion or len(suggestion) > QUESTION_MAX_LENGTH:
        raise ValueError("润色结果无效")
    for token in _SCIENTIFIC_TOKEN.findall(original):
        if not re.search(r"(?<![A-Za-z0-9_])" + re.escape(token) + r"(?![A-Za-z0-9_])", suggestion):
            raise ValueError("润色结果遗漏了原问题的数值或术语")
    return suggestion


def polish_prompt(draft: str) -> str:
    """仅改写草稿，不调用检索或写入问答历史。"""
    original = draft.strip()
    if not original or len(draft) > QUESTION_MAX_LENGTH:
        raise ValueError("提示词长度无效")
    config = get_llm_config()
    if not config.api_key:
        raise RagChatUnavailableError("LLM 问答未配置")
    response = get_llm_client(read_timeout=30).chat.completions.create(
        model=config.model,
        messages=[
            {"role": "system", "content": _POLISH_TEMPLATE.read_text(encoding="utf-8").split("-->", 1)[-1].strip()},
            {"role": "user", "content": json.dumps({"originalPrompt": original}, ensure_ascii=False)},
        ],
        temperature=0.2,
        max_tokens=POLISH_MAX_TOKENS,
    )
    return validate_polish_response(original, response)


def _loads_json(value: str | None, fallback: Any) -> Any:
    if value is None:
        return fallback
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback


def health() -> dict[str, Any]:
    settings = get_rag_settings()
    database_available = settings.database_available

    # 检查 Qdrant 连接
    qdrant_available = False
    try:
        from backend.rag.qdrant_connection import create_qdrant_client
        from contextlib import closing
        with closing(create_qdrant_client()) as client:
            client.get_collections()
        qdrant_available = True
    except Exception:
        pass

    # 健康检查也位于请求上下文内；这样用户自带凭据不会被服务端默认配置覆盖。
    chat_available = bool(get_llm_config().api_key)
    available = database_available and qdrant_available

    if not available:
        message = "AI 文献助手数据不可用"
    elif not chat_available:
        message = "RAG 检索可用，LLM 问答未配置"
    else:
        message = "AI 文献助手已就绪"

    return {
        "available": available,
        "database_available": database_available,
        "qdrant_available": qdrant_available,
        "chat_available": chat_available,
        "message": message,
    }


def _ensure_data_available() -> None:
    status = health()
    if not status["available"]:
        raise RagDataUnavailableError("AI 文献助手数据不可用")


def _ensure_chat_available() -> None:
    _ensure_data_available()
    if not get_llm_config().api_key:
        raise RagChatUnavailableError("LLM 问答未配置")


async def search(query: str, top_k: int = 10, mode: str | None = None) -> dict[str, Any]:
    _ensure_data_available()
    try:
        from backend.rag.search.engine import search as rag_search

        return await rag_search(query, mode=mode, top_k=top_k)
    except (RagDataUnavailableError, RagChatUnavailableError, UserCredentialError):
        raise
    except Exception as exc:
        raise RagInternalError(str(exc)) from exc


def detect_search_mode(query: str) -> dict[str, str]:
    try:
        from backend.rag.search.engine import SEARCH_MODES, detect_search_mode as detect

        mode = detect(query)
        return {"query": query, "mode": mode, "description": SEARCH_MODES.get(mode, "")}
    except Exception as exc:
        raise RagInternalError(str(exc)) from exc


async def chat(
    question: str,
    top_k: int = 15,
    rerank_top_k: int = 5,
    history: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    # 普通问答与流式问答共享 Mentor 路径，避免进入另一套探索流程。
    async for event in chat_stream(question, top_k=top_k, rerank_top_k=rerank_top_k, history=history):
        if event.get("type") == "done":
            return dict(event.get("data") or {})
    raise RagInternalError("问答未返回完成结果")


async def chat_stream(
    question: str,
    top_k: int = 15,
    rerank_top_k: int = 5,
    history: list[dict[str, str]] | None = None,
    explore: bool = False,
) -> AsyncIterator[dict[str, Any]]:
    _ensure_chat_available()

    if explore:
        # 探索模式 — Inspiration Agent (多轮，在线程池中运行)
        try:
            from backend.rag.agent import run
            from langchain_core.messages import HumanMessage, AIMessage

            prev_msgs = None
            if history:
                prev_msgs = []
                for h in history[-20:]:
                    role = h.get("role", "user")
                    content = h.get("content", "")
                    if role == "assistant":
                        prev_msgs.append(AIMessage(content=content))
                    else:
                        prev_msgs.append(HumanMessage(content=content))

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                ctx = contextvars.copy_context()
                result = await asyncio.get_event_loop().run_in_executor(
                    pool, ctx.run, run, question, prev_msgs
                )

            answer = result.get("answer", "")
            # 流式输出
            for char in answer:
                yield {"type": "token", "data": char}

            yield {
                "type": "done",
                "data": {
                    "answer": answer,
                    "source": f"inspire_{result.get('mode', '')}",
                    "ideas": result.get("ideas", []),
                    "provider": get_llm_config().provider,
                    "model": get_llm_config().model,
                },
            }
            return
        except (RagDataUnavailableError, RagChatUnavailableError, UserCredentialError):
            raise
        except Exception as exc:
            raise RagInternalError(str(exc)) from exc

    # 普通问答 — Mentor Agent
    try:
        from backend.rag.agent.mentor import run_stream

        # history → LangChain 消息格式
        from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
        prev_msgs = None
        if history:
            prev_msgs = []
            for h in history[-20:]:
                role = h.get("role", "user")
                content = h.get("content", "")
                if role == "assistant":
                    prev_msgs.append(AIMessage(content=content))
                elif role == "system":
                    prev_msgs.append(SystemMessage(content=content))
                else:
                    prev_msgs.append(HumanMessage(content=content))

        async for event in run_stream(question, prev_messages=prev_msgs):
            if event.get("type") == "done":
                data = dict(event.get("data") or {})
                data.setdefault("provider", get_llm_config().provider)
                data.setdefault("model", get_llm_config().model)
                event = {**event, "data": data}
            yield event
    except (RagDataUnavailableError, RagChatUnavailableError, UserCredentialError):
        raise
    except Exception as exc:
        raise RagInternalError(str(exc)) from exc


async def stats() -> dict[str, Any]:
    _ensure_data_available()
    try:
        from backend.rag.database import async_session_factory
        from backend.models import Paper, PaperChunk
        from backend.rag.vectordb import collection_stats
        from backend.rag.search.property_records import approved_paper_conditions, database_counts

        async with async_session_factory() as session:
            counts = await database_counts(session)
            chunk_count = await session.scalar(
                select(func.count(PaperChunk.id)).join(Paper, Paper.id == PaperChunk.paper_id)
                .where(*approved_paper_conditions())
            )
            paper_type_rows = (await session.execute(
                select(Paper.paper_type, func.count()).where(*approved_paper_conditions()).group_by(Paper.paper_type)
            )).all()

        try:
            qdrant_chunks = collection_stats().get("count", 0)
        except Exception:
            qdrant_chunks = 0

        return {
            "papers": counts["papers"],
            "superconductors": counts["superconductors"],
            "records": counts["records"],
            "chunks": chunk_count,
            "qdrant_chunks": qdrant_chunks,
            "chemical_systems": counts["chemical_systems"],
            "paper_types": {row[0] or "unknown": row[1] for row in paper_type_rows},
        }
    except Exception as exc:
        raise RagInternalError(str(exc)) from exc


async def list_papers(keyword: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
    _ensure_data_available()
    try:
        from backend.rag.database import async_session_factory
        from backend.models import Paper
        from backend.rag.search.sql_search import search_papers
        from backend.rag.search.property_records import approved_paper_conditions

        async with async_session_factory() as session:
            if keyword:
                return await search_papers(session, keyword, limit=limit)

            result = await session.execute(
                select(Paper)
                .where(*approved_paper_conditions())
                .order_by(desc(Paper.year), desc(Paper.id))
                .limit(limit)
            )
            return [
                {
                    "type": "paper",
                    "id": paper.id,
                    "doi": paper.doi,
                    "title": paper.title,
                    "authors": paper.authors,
                    "journal": paper.journal,
                    "year": paper.year,
                    "summary": paper.summary,
                    "paper_type": paper.paper_type,
                }
                for paper in result.scalars()
            ]
    except Exception as exc:
        raise RagInternalError(str(exc)) from exc


async def paper_detail(paper_id: int) -> dict[str, Any]:
    _ensure_data_available()
    try:
        from backend.rag.database import async_session_factory
        from backend.rag.search.sql_search import get_paper_detail

        async with async_session_factory() as session:
            detail = await get_paper_detail(session, paper_id)
        if detail is None:
            raise RagNotFoundError("论文不存在")
        return detail
    except RagNotFoundError:
        raise
    except Exception as exc:
        raise RagInternalError(str(exc)) from exc


async def search_superconductors(
    formula: str | None = None,
    elements: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    _ensure_data_available()
    try:
        from backend.rag.database import async_session_factory
        from backend.models import Superconductor
        from backend.rag.search.sql_search import search_by_elements_exact, search_by_formula, _format_superconductors
        from backend.rag.search.property_records import approved_materials_statement

        async with async_session_factory() as session:
            if formula:
                return await search_by_formula(session, formula)
            if elements:
                parsed = [part.strip() for part in elements.replace(",", "-").split("-") if part.strip()]
                return await search_by_elements_exact(session, parsed)

            result = await session.execute(approved_materials_statement().order_by(Superconductor.id).limit(limit))
            return await _format_superconductors(session, result.scalars().all())
    except Exception as exc:
        raise RagInternalError(str(exc)) from exc


async def superconductor_detail(superconductor_id: int) -> dict[str, Any]:
    _ensure_data_available()
    try:
        from backend.rag.database import async_session_factory
        from backend.models import Superconductor
        from backend.rag.search.sql_search import get_superconductor_records
        from backend.rag.search.property_records import approved_materials_statement

        async with async_session_factory() as session:
            result = await session.execute(
                approved_materials_statement()
                .where(Superconductor.id == superconductor_id)
                .options(
                    joinedload(Superconductor.chemical_system),
                )
            )
            sc = result.unique().scalar_one_or_none()
            if sc is None:
                raise RagNotFoundError("超导体不存在")

            return {
                "type": "superconductor",
                "id": sc.id,
                "chemical_system_id": sc.chemical_system_id,
                "chemical_system": sc.chemical_system.system_key if sc.chemical_system else None,
                "chemical_formula": sc.chemical_formula,
                "formula_normalized": sc.formula_normalized,
                "display_name": sc.display_name,
                "elements_list": _loads_json(sc.elements_list, []),
                "composition": _loads_json(sc.composition, {}),
                "element_ratio": _loads_json(sc.element_ratio, {}),
                "properties": await get_superconductor_records(session, sc.id),
            }
    except RagNotFoundError:
        raise
    except Exception as exc:
        raise RagInternalError(str(exc)) from exc


async def upload_pdf(file_path: Path, original_filename: str, uploaded_by_user_id: int | None = None) -> dict[str, Any]:
    _ensure_chat_available()
    try:
        from backend.ingest.pipeline import ingest_pdf
    except ModuleNotFoundError as exc:
        raise RagInternalError("PDF 摄入模块尚未接入") from exc

    try:
        return await ingest_pdf(file_path=file_path, original_filename=original_filename,
                                uploaded_by_user_id=uploaded_by_user_id)
    except Exception as exc:
        raise RagInternalError(str(exc)) from exc

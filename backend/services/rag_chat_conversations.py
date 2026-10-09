"""RAG 云端会话的所有权、完成轮次和本地历史导入。"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.models import RagChatConversation, RagChatTurn


class ConversationNotFound(Exception):
    pass


class ConversationConflict(Exception):
    pass


def _owned(db: Session, owner_id: int, conversation_id: str, *, lock: bool = False) -> RagChatConversation:
    query = select(RagChatConversation).where(
        RagChatConversation.id == conversation_id,
        RagChatConversation.owner_user_id == owner_id,
    )
    conversation = db.scalar(query.with_for_update() if lock else query)
    if conversation is None:
        raise ConversationNotFound()
    return conversation


def _sequence(db: Session, conversation_id: str) -> int:
    return int(db.scalar(select(func.max(RagChatTurn.sequence)).where(
        RagChatTurn.conversation_id == conversation_id,
    )) or 0)


def _summary(db: Session, conversation: RagChatConversation) -> dict:
    return {
        "id": conversation.id, "title": conversation.title,
        "created_at": conversation.created_at.isoformat(),
        "updated_at": conversation.updated_at.isoformat(),
        "last_sequence": _sequence(db, conversation.id),
    }


def _turn(turn: RagChatTurn) -> dict:
    return {
        "id": turn.id, "sequence": turn.sequence, "request_id": turn.request_id,
        "question": turn.question, "answer": turn.answer,
        "citations": turn.citations_json or [], "display_meta": turn.display_meta_json or {},
    }


def create(db: Session, owner_id: int, title: str = "新对话") -> dict:
    conversation = RagChatConversation(
        id=uuid.uuid4().hex, owner_user_id=owner_id, title=title.strip()[:200] or "新对话",
        updated_at=datetime.now(timezone.utc),
    )
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return _summary(db, conversation)


def list_for_user(db: Session, owner_id: int, *, limit: int = 50, offset: int = 0) -> list[dict]:
    rows = db.scalars(select(RagChatConversation).where(
        RagChatConversation.owner_user_id == owner_id,
    ).order_by(RagChatConversation.updated_at.desc(), RagChatConversation.id.desc()).limit(limit).offset(offset)).all()
    return [_summary(db, row) for row in rows]


def detail(db: Session, owner_id: int, conversation_id: str) -> dict:
    conversation = _owned(db, owner_id, conversation_id)
    turns = db.scalars(select(RagChatTurn).where(
        RagChatTurn.conversation_id == conversation.id,
    ).order_by(RagChatTurn.sequence)).all()
    return {**_summary(db, conversation), "turns": [_turn(turn) for turn in turns]}


def delete(db: Session, owner_id: int, conversation_id: str) -> None:
    conversation = _owned(db, owner_id, conversation_id)
    db.delete(conversation)
    db.commit()


def prepare(db: Session, owner_id: int, conversation_id: str, request_id: str, expected_sequence: int) -> dict:
    _owned(db, owner_id, conversation_id)
    existing = db.scalar(select(RagChatTurn).where(
        RagChatTurn.conversation_id == conversation_id, RagChatTurn.request_id == request_id,
    ))
    if existing is not None:
        return {"completed": _turn(existing)}
    if _sequence(db, conversation_id) != expected_sequence:
        raise ConversationConflict()
    turns = db.scalars(select(RagChatTurn).where(
        RagChatTurn.conversation_id == conversation_id,
    ).order_by(RagChatTurn.sequence.desc()).limit(10)).all()
    history = []
    for turn in reversed(turns):
        history.extend([{"role": "user", "content": turn.question}, {"role": "assistant", "content": turn.answer}])
    return {"history": history}


def _safe_meta(data: dict) -> tuple[list, dict]:
    citations = []
    for item in (data.get("citations") or [])[:50]:
        if isinstance(item, dict) and isinstance(item.get("paper_id"), int):
            citations.append({
                "paper_id": item["paper_id"],
                "source_kind": str(item.get("source_kind") or "")[:64],
                "attribution": str(item.get("attribution") or "")[:1000],
            })
    meta = {key: data[key] for key in ("papers", "top10", "ideas", "reviews", "inspiration") if key in data}
    if len(json.dumps(meta, ensure_ascii=False)) > 100_000:
        meta = {}
    return citations, meta


def complete(db: Session, owner_id: int, conversation_id: str, request_id: str,
             expected_sequence: int, question: str, answer: str, data: dict) -> dict:
    if not answer.strip() or len(answer) > 100_000:
        raise ValueError("回答长度无效")
    conversation = _owned(db, owner_id, conversation_id, lock=True)
    existing = db.scalar(select(RagChatTurn).where(
        RagChatTurn.conversation_id == conversation_id, RagChatTurn.request_id == request_id,
    ))
    if existing is not None:
        return _turn(existing)
    if _sequence(db, conversation_id) != expected_sequence:
        raise ConversationConflict()
    citations, meta = _safe_meta(data)
    turn = RagChatTurn(
        conversation_id=conversation_id, sequence=expected_sequence + 1,
        request_id=request_id, question=question, answer=answer,
        citations_json=citations, display_meta_json=meta,
    )
    db.add(turn)
    if expected_sequence == 0 and conversation.title == "新对话":
        conversation.title = question.strip()[:80] or "新对话"
    conversation.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(turn)
    return _turn(turn)


def import_local(db: Session, owner_id: int, source_local_id: str, title: str, messages: list[dict]) -> dict:
    if any(item.get("role") == "user" and len(item.get("content", "")) > 1000 for item in messages):
        raise ValueError("旧会话问题超过长度上限")
    existing = db.scalar(select(RagChatConversation).where(
        RagChatConversation.owner_user_id == owner_id,
        RagChatConversation.source_local_id == source_local_id,
    ))
    if existing is not None:
        return _summary(db, existing)
    conversation = RagChatConversation(
        id=uuid.uuid4().hex, owner_user_id=owner_id,
        source_local_id=source_local_id[:128], title=title.strip()[:200] or "旧会话",
        updated_at=datetime.now(timezone.utc),
    )
    db.add(conversation)
    sequence = 0
    for question, answer in zip(messages[::2], messages[1::2]):
        if question.get("role") != "user" or answer.get("role") != "assistant":
            continue
        if not question.get("content", "").strip() or not answer.get("content", "").strip():
            continue
        sequence += 1
        citations, _ = _safe_meta({"citations": answer.get("citations", [])})
        db.add(RagChatTurn(
            conversation_id=conversation.id, sequence=sequence,
            request_id=f"import-{sequence}", question=question["content"],
            answer=answer["content"], citations_json=citations, display_meta_json={},
        ))
    db.commit()
    db.refresh(conversation)
    return _summary(db, conversation)

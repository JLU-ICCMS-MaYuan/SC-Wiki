"""共享社区元数据；Go 承担读取与治理，Python 承担 AI 生成生命周期。"""
from sqlalchemy import Boolean, JSON, Column, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.mysql import MEDIUMTEXT
from sqlalchemy.sql import func
from backend.database import Base


class CommunitySystem(Base):
    __tablename__ = "community_systems"
    system_key = Column(String(100), primary_key=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())


class CommunityEntry(Base):
    __tablename__ = "community_entries"
    __table_args__ = (
        Index("ix_community_question", "kind", "status", "activity_at", "id"),
        Index("ix_community_answer", "question_id", "kind", "status", "id"),
        Index("ix_community_answer_comments", "answer_id", "kind", "id"),
        Index("ix_community_paper", "paper_id", "kind", "status", "id"),
        Index("ix_community_system", "system_key", "kind", "status", "id"),
    )
    id = Column(Integer, primary_key=True, autoincrement=True)
    kind = Column(String(16), nullable=False)
    title = Column(String(200), nullable=False, server_default="")
    body = Column(Text().with_variant(MEDIUMTEXT(), "mysql"), nullable=False)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    origin = Column(String(16), nullable=False, server_default="human")
    category = Column(String(64), nullable=False, server_default="")
    model_id = Column(String(64), nullable=False, server_default="")
    model_name = Column(String(200), nullable=False, server_default="")
    model = Column(String(200), nullable=False, server_default="")
    model_order = Column(Integer, nullable=False, server_default="0")
    citations = Column(JSON, nullable=True)
    human_edited = Column(Boolean, nullable=False, server_default="0")
    revision = Column(Integer, nullable=False, server_default="1")
    question_hash = Column(String(64), unique=True, nullable=True)
    question_id = Column(Integer, ForeignKey("community_entries.id", ondelete="CASCADE"))
    answer_id = Column(Integer, ForeignKey("community_entries.id", ondelete="CASCADE"))
    paper_id = Column(Integer, ForeignKey("papers.id", ondelete="CASCADE"))
    system_key = Column(String(100), ForeignKey("community_systems.system_key"))
    parent_id = Column(Integer, ForeignKey("community_entries.id", ondelete="SET NULL"))
    reply_to_id = Column(Integer, ForeignKey("community_entries.id", ondelete="SET NULL"))
    status = Column(String(16), nullable=False, server_default="visible")
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now())
    activity_at = Column(DateTime, nullable=False, server_default=func.now())


class CommunityVote(Base):
    __tablename__ = "community_votes"
    entry_id = Column(Integer, ForeignKey("community_entries.id", ondelete="CASCADE"), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())


class CommunityReport(Base):
    __tablename__ = "community_reports"
    __table_args__ = (UniqueConstraint("entry_id", "reporter_id", name="uq_community_report"),)
    id = Column(Integer, primary_key=True, autoincrement=True)
    entry_id = Column(Integer, ForeignKey("community_entries.id", ondelete="CASCADE"), nullable=False)
    reporter_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    reason = Column(Text, nullable=False)
    status = Column(String(16), nullable=False, server_default="pending", index=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    resolved_at = Column(DateTime)


class CommunityModerationEvent(Base):
    __tablename__ = "community_moderation_events"
    id = Column(Integer, primary_key=True, autoincrement=True)
    entry_id = Column(Integer, ForeignKey("community_entries.id", ondelete="CASCADE"), nullable=False, index=True)
    actor_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    action = Column(String(16), nullable=False)
    reason = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())


class CommunityNotification(Base):
    __tablename__ = "community_notifications"
    __table_args__ = (Index("ix_community_notifications_recipient", "recipient_id", "read_at", "id"),)
    id = Column(Integer, primary_key=True, autoincrement=True)
    recipient_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    actor_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    entry_id = Column(Integer, ForeignKey("community_entries.id", ondelete="CASCADE"), nullable=False)
    kind = Column(String(16), nullable=False)
    read_at = Column(DateTime)
    created_at = Column(DateTime, nullable=False, server_default=func.now())


class CommunityAIBatch(Base):
    __tablename__ = "community_ai_batches"
    id = Column(String(36), primary_key=True)
    actor_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    request_hash = Column(String(64), nullable=False)
    question_id = Column(Integer, ForeignKey("community_entries.id"), unique=True)
    state = Column(String(16), nullable=False, default="queued")
    error = Column(String(64), nullable=False, default="")
    category = Column(String(64), nullable=False, default="")
    question_model_id = Column(String(64), nullable=False)
    sources = Column(JSON, nullable=True)
    job_id = Column(String(80), nullable=False, default="")
    attempt = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    started_at = Column(DateTime)
    finished_at = Column(DateTime)


class CommunityAITask(Base):
    __tablename__ = "community_ai_tasks"
    __table_args__ = (UniqueConstraint("batch_id", "model_id", name="uq_community_ai_model"),)
    id = Column(Integer, primary_key=True, autoincrement=True)
    batch_id = Column(String(36), ForeignKey("community_ai_batches.id"), nullable=False, index=True)
    model_id = Column(String(64), nullable=False)
    model_name = Column(String(200), nullable=False)
    model = Column(String(200), nullable=False)
    config_hash = Column(String(64), nullable=False)
    model_order = Column(Integer, nullable=False)
    answer_id = Column(Integer, ForeignKey("community_entries.id"), unique=True)
    state = Column(String(16), nullable=False, default="queued")
    error = Column(String(64), nullable=False, default="")
    job_id = Column(String(80), nullable=False, default="")
    attempt = Column(Integer, nullable=False, default=0)
    question_revision = Column(Integer, nullable=False, default=1)
    answer_revision = Column(Integer, nullable=False, default=0)
    started_at = Column(DateTime)
    finished_at = Column(DateTime)


class CommunityEntryRevision(Base):
    __tablename__ = "community_entry_revisions"
    __table_args__ = (UniqueConstraint("entry_id", "revision", name="uq_community_revision"),)
    id = Column(Integer, primary_key=True, autoincrement=True)
    entry_id = Column(Integer, ForeignKey("community_entries.id"), nullable=False)
    revision = Column(Integer, nullable=False)
    body = Column(Text().with_variant(MEDIUMTEXT(), "mysql"), nullable=False)
    citations = Column(JSON)
    human_edited = Column(Boolean, nullable=False)
    actor_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, nullable=False, server_default=func.now())


class CommunityModelAnswer(Base):
    __tablename__ = "community_model_answers"
    __table_args__ = (UniqueConstraint("question_id", "config_hash", name="uq_community_model_card"),)
    id = Column(Integer, primary_key=True)
    question_id = Column(Integer, ForeignKey("community_entries.id"), nullable=False)
    config_hash = Column(String(64), nullable=False)
    entry_id = Column(Integer, ForeignKey("community_entries.id"), nullable=False, unique=True)
    first_sequence = Column(Integer, nullable=False)


class CommunityAnswerRequest(Base):
    __tablename__ = "community_answer_requests"
    __table_args__ = (UniqueConstraint("question_id", "sequence", name="uq_community_answer_sequence"),)
    id = Column(Integer, primary_key=True, autoincrement=True)
    request_id = Column(String(36), nullable=False, unique=True)
    question_id = Column(Integer, ForeignKey("community_entries.id"), nullable=False, index=True)
    sequence = Column(Integer, nullable=False)
    actor_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    model_id = Column(String(64), nullable=False)
    model_name = Column(String(200), nullable=False)
    model = Column(String(200), nullable=False)
    config_hash = Column(String(64), nullable=False)
    state = Column(String(16), nullable=False, default="queued")
    error = Column(String(64), nullable=False, default="")
    job_id = Column(String(80), nullable=False)
    retry_of = Column(Integer, ForeignKey("community_answer_requests.id"))
    answer_id = Column(Integer, ForeignKey("community_entries.id"))
    turn_id = Column(Integer)
    context_snapshot = Column(JSON)
    sources = Column(JSON)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    started_at = Column(DateTime)
    finished_at = Column(DateTime)


class CommunityAnswerTurn(Base):
    __tablename__ = "community_answer_turns"
    id = Column(Integer, primary_key=True, autoincrement=True)
    entry_id = Column(Integer, ForeignKey("community_entries.id"), nullable=False, index=True)
    request_id = Column(Integer, ForeignKey("community_answer_requests.id"), nullable=False, unique=True)
    body = Column(Text().with_variant(MEDIUMTEXT(), "mysql"), nullable=False)
    citations = Column(JSON)
    replies = Column(JSON)
    revision = Column(Integer, nullable=False, default=1)
    human_edited = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now())


class CommunityTurnRevision(Base):
    __tablename__ = "community_answer_turn_revisions"
    __table_args__ = (UniqueConstraint("turn_id", "revision", name="uq_community_turn_revision"),)
    id = Column(Integer, primary_key=True, autoincrement=True)
    turn_id = Column(Integer, ForeignKey("community_answer_turns.id"), nullable=False)
    revision = Column(Integer, nullable=False)
    body = Column(Text().with_variant(MEDIUMTEXT(), "mysql"), nullable=False)
    citations = Column(JSON)
    replies = Column(JSON)
    human_edited = Column(Boolean, nullable=False)
    actor_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

"""Shared metadata for community tables. Business rules live in the Go service."""
from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
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
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
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

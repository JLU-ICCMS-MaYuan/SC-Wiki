"""当前工作稿、采用资料与正式交接；旧历史表不删除或改写。"""
from sqlalchemy import Column, String, Integer, BigInteger, JSON, DateTime, Text, ForeignKey, Index, UniqueConstraint
from sqlalchemy.sql import func
from backend.database import Base


class ScientificSourceItem(Base):
    __tablename__ = "scientific_source_items"
    id = Column(String(64), primary_key=True)
    namespace = Column(String(128), nullable=False, index=True)
    payload = Column(JSON, nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())


class ScientificFieldSourceUse(Base):
    __tablename__ = "scientific_field_source_uses"
    work_key = Column(String(128), primary_key=True)
    item_key = Column(String(64), primary_key=True)
    source_id = Column(String(64), ForeignKey("scientific_source_items.id", ondelete="RESTRICT"), primary_key=True)
    role = Column(String(16), primary_key=True)
    binding_json = Column(JSON, nullable=False, default=dict)
    __table_args__ = (Index("ix_field_source_use_source", "source_id"),)


class ScientificWorkDraft(Base):
    __tablename__ = "scientific_work_drafts"
    id = Column(String(64), primary_key=True)
    document_key = Column(String(128), nullable=False, index=True)
    target = Column(String(16), nullable=False)
    target_id = Column(String(64), nullable=False)
    owner_id = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    write_epoch = Column(String(32), nullable=False)
    revision = Column(BigInteger, nullable=False, default=1)
    body = Column(JSON, nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
    __table_args__ = (UniqueConstraint("target", "target_id", name="uq_work_draft_target"),)

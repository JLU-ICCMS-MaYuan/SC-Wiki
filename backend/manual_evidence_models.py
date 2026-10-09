"""按字段和值版本保存人工修改说明及独立证据。"""

from sqlalchemy import JSON, Column, DateTime, Index, Integer, String, Text
from sqlalchemy.sql import func

from backend.database import Base


class ScientificManualEvidence(Base):
    __tablename__ = "scientific_manual_evidence"
    __table_args__ = (
        Index("ix_manual_evidence_target_field", "target", "target_id", "item_key"),
        Index("ix_manual_evidence_paper_revision", "paper_id", "paper_revision"),
    )

    id = Column(String(32), primary_key=True)
    target = Column(String(16), nullable=False)
    target_id = Column(String(64), nullable=False)
    paper_id = Column(Integer)
    paper_revision = Column(Integer)
    item_key = Column(String(64), nullable=False)
    baseline_hash = Column(String(64), nullable=False)
    value_hash = Column(String(64), nullable=False)
    source_hash = Column(String(64), nullable=False)
    before_value = Column(JSON)
    after_value = Column(JSON)
    actor_user_id = Column(Integer, nullable=False)
    actor_name_snapshot = Column(String(100))
    reason = Column(Text, nullable=False, default="")
    no_evidence_reason = Column(Text, nullable=False, default="")
    items = Column(JSON, nullable=False, default=list)
    status = Column(String(16), nullable=False, default="draft")
    evidence_version = Column(Integer, nullable=False, default=1, server_default="1")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

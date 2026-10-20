"""论文独立结构资料；与材料状态的规范几何分开保存。"""

import uuid
from sqlalchemy import (
    Column,
    String,
    Integer,
    JSON,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    Index,
    CheckConstraint,
    Numeric,
    func,
)
from backend.database import Base


class PaperStructuralRecord(Base):
    __tablename__ = "paper_structural_records"
    __table_args__ = (
        UniqueConstraint(
            "paper_id", "paper_revision", "record_key", name="uq_paper_structure_record_revision"
        ),
        CheckConstraint("kind IN ('model', 'lattice', 'issue')", name="ck_paper_structure_record_kind"),
        CheckConstraint(
            "retention IN ('pending', 'retained', 'excluded')", name="ck_paper_structure_record_retention"
        ),
        Index("ix_paper_structure_record_paper", "paper_id", "paper_revision"),
        Index("ix_paper_structure_record_system", "system_key", "retention"),
    )
    id = Column(String(32), primary_key=True, default=lambda: uuid.uuid4().hex)
    paper_id = Column(Integer, ForeignKey("papers.id", ondelete="CASCADE"), nullable=False)
    paper_revision = Column(Integer, nullable=False)
    record_key = Column(String(128), nullable=False)
    kind = Column(String(16), nullable=False)
    material = Column(String(255), nullable=False)
    system_key = Column(String(255), nullable=False)
    elements = Column(JSON, nullable=False)
    pressure_gpa = Column(Numeric(20, 8))
    space_group = Column(String(100))
    state_key = Column(String(128))
    retention = Column(String(16), nullable=False)
    data_json = Column(JSON, nullable=False)
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

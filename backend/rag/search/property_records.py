"""RAG 结构化数据的统一读取与输出；只读取当前已批准的论文版本。"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import and_, func, or_, select

from backend.models import ChemicalSystem, MaterialState, Paper, PropertyRecord, Superconductor


def approved_paper_conditions():
    return (Paper.review_status == "approved", Paper.approved_revision == Paper.content_revision)


def approved_materials_statement():
    return select(Superconductor).join(Paper, and_(
        Paper.id == Superconductor.paper_id,
        Paper.content_revision == Superconductor.paper_revision,
    )).where(*approved_paper_conditions())


def property_records_statement():
    """记录、状态和材料必须属于同一论文版本；允许只有材料名的状态。"""
    return (
        select(PropertyRecord, MaterialState, Paper, Superconductor)
        .join(MaterialState, and_(
            MaterialState.id == PropertyRecord.material_state_id,
            MaterialState.paper_id == PropertyRecord.paper_id,
            MaterialState.paper_revision == PropertyRecord.paper_revision,
        ))
        .join(Paper, and_(
            Paper.id == PropertyRecord.paper_id,
            Paper.content_revision == PropertyRecord.paper_revision,
        ))
        .outerjoin(Superconductor, and_(
            Superconductor.id == MaterialState.superconductor_id,
            Superconductor.paper_id == PropertyRecord.paper_id,
            Superconductor.paper_revision == PropertyRecord.paper_revision,
        ))
        .where(*approved_paper_conditions())
        .where(or_(MaterialState.superconductor_id.is_(None), Superconductor.id.isnot(None)))
    )


def _number(value):
    return float(value) if isinstance(value, Decimal) else value


def format_property_record(record, state, paper, material) -> dict:
    """保留原值和完整范围，不把范围中点伪装成论文报告的单值。"""
    values = {
        "number": _number(record.value_number),
        "range": None,
        "text": record.value_text,
        "boolean": record.value_boolean,
    }
    value = values[record.value_kind]
    minimum, maximum = _number(record.value_min), _number(record.value_max)
    display_value = f"{minimum}–{maximum}" if record.value_kind == "range" else str(value)
    return {
        "id": record.id, "record_key": record.record_key,
        "paper_id": paper.id, "paper_revision": record.paper_revision,
        "material_state_id": state.id,
        "superconductor_id": material.id if material else None,
        "material": state.material_name or (material.chemical_formula or material.display_name if material else ""),
        "chemical_formula": material.chemical_formula if material else None,
        "name": record.property_code, "label": record.name_raw, "name_raw": record.name_raw,
        "record_type": record.record_type, "property_code": record.property_code,
        "custom_property_key": record.custom_property_key,
        "definition_key": record.definition_key, "definition_version": record.definition_version,
        "value_kind": record.value_kind, "value": value,
        "value_min": minimum, "value_max": maximum, "value_raw": record.value_raw,
        "display_value": display_value, "unit": record.canonical_unit or record.unit_raw,
        "unit_raw": record.unit_raw, "uncertainty": _number(record.uncertainty),
        "pressure_gpa": _number(state.pressure_value_gpa),
        "pressure_min_gpa": _number(state.pressure_min_gpa),
        "pressure_max_gpa": _number(state.pressure_max_gpa), "pressure_raw": state.pressure_raw,
        "temperature_k": _number(state.temperature_value_k),
        "condition_note": state.note, "is_primary": record.is_representative,
        "method_code": record.method_code, "method_raw": record.method_raw,
        "superconductor_type": state.state_kind, "article_type": paper.paper_type,
        "source_label": "SC-Wiki", "payload": record.payload_json,
        "paper_doi": paper.doi, "paper_title": paper.title, "paper_year": paper.year,
    }


async def database_counts(session) -> dict:
    """所有数量遵守与问答相同的批准版本边界。"""
    materials = approved_materials_statement().subquery()
    records = property_records_statement().subquery()
    systems = select(ChemicalSystem.id).join(Paper, and_(
        Paper.id == ChemicalSystem.paper_id,
        Paper.content_revision == ChemicalSystem.paper_revision,
    )).where(*approved_paper_conditions()).subquery()
    return {
        "papers": await session.scalar(select(func.count(Paper.id)).where(*approved_paper_conditions())),
        "superconductors": await session.scalar(select(func.count()).select_from(materials)),
        "records": await session.scalar(select(func.count()).select_from(records)),
        "chemical_systems": await session.scalar(select(func.count()).select_from(systems)),
    }

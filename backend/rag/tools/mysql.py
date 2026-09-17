"""RAG 物性查询服务：统一读取当前已批准的 PropertyRecord。"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from sqlalchemy import func, or_

from backend.models import MaterialState, PropertyRecord, Superconductor
from backend.rag.database import async_session_factory
from backend.rag.search.property_records import (
    database_counts, format_property_record, property_records_statement,
)
from backend.rag.search.sql_search import _normalize_formula

# 对外别名只在此处转换，避免 Agent 与数据库层重复维护映射。
PROPERTY_ALIASES = {
    "Tc": "tc", "critical_temperature": "tc", "超导温度(AD)": "tc",
    "超导温度": "tc", "临界温度": "tc",
    "lambda": "electron_phonon_coupling", "电声耦合lambda": "electron_phonon_coupling",
    "电声耦合": "electron_phonon_coupling", "德拜温度": "debye_temperature",
    "上临界磁场": "upper_critical_field", "超导能隙": "superconducting_gap",
    "压力": "pressure",
}


async def search_property_records(
    predicate: str | None = None,
    operator: str = "=",
    value: str | None = None,
    *,
    material: str | None = None,
) -> list[dict]:
    """按物性名称/代码、数值条件和材料读取记录。

    不传 value 时保留数值、范围、文本和布尔记录。范围按上界比较，返回完整范围；
    pressure 筛选材料状态的压力，不将压力误写成物性值。参数仍属于各自记录的 payload。
    """
    if operator not in {"=", ">", "<", ">=", "<="}:
        raise ValueError("比较条件只支持 =、>、<、>=、<=")
    threshold = None
    if value is not None:
        try:
            threshold = Decimal(str(value))
        except InvalidOperation as exc:
            raise ValueError("比较条件必须包含有效数值") from exc
        if not threshold.is_finite():
            raise ValueError("比较条件必须包含有限数值")

    canonical = PROPERTY_ALIASES.get(predicate, predicate)
    stmt = property_records_statement()
    numeric = func.coalesce(PropertyRecord.value_number, PropertyRecord.value_max)
    if canonical == "pressure":
        numeric = func.coalesce(MaterialState.pressure_value_gpa, MaterialState.pressure_max_gpa)
        stmt = stmt.where(numeric.isnot(None))
    elif canonical:
        stmt = stmt.where(or_(
            PropertyRecord.property_code == canonical,
            PropertyRecord.name_raw == canonical,
            PropertyRecord.custom_property_key == canonical,
        ))
    if threshold is not None:
        if canonical != "pressure":
            stmt = stmt.where(PropertyRecord.value_kind.in_(("number", "range")))
        comparison = {
            "=": numeric == threshold, ">": numeric > threshold, "<": numeric < threshold,
            ">=": numeric >= threshold, "<=": numeric <= threshold,
        }[operator]
        stmt = stmt.where(comparison)
    if material:
        matches = [Superconductor.chemical_formula == material,
                   Superconductor.display_name == material, MaterialState.material_name == material]
        normalized = _normalize_formula(material)
        if normalized:
            matches.append(Superconductor.formula_normalized == normalized)
        stmt = stmt.where(or_(*matches))
    stmt = stmt.order_by(numeric.desc(), PropertyRecord.id)
    async with async_session_factory() as session:
        rows = (await session.execute(stmt)).all()
    result = []
    for row in rows:
        item = format_property_record(*row)
        item.update(subject=item["material"], predicate=predicate or item["label"],
                    property_name=item["property_code"], object=item["display_value"])
        if canonical == "pressure":
            pressure = item["pressure_gpa"]
            if pressure is None:
                item["object"] = f"{item['pressure_min_gpa']}–{item['pressure_max_gpa']}"
            else:
                item["object"] = str(pressure)
            item["queried_unit"] = "GPa"
        result.append(item)
    return result


async def get_all_properties(subject: str) -> list[dict]:
    """保留材料全部记录及各自来源、条件与类型，不再折叠为无来源的字符串。"""
    return await search_property_records(material=subject)


async def get_material_context(formula: str) -> dict:
    """材料工具与知识图谱材料接口共用权威物性来源。"""
    records = await search_property_records(material=formula)
    papers = {r["paper_id"]: {"id": r["paper_id"], "title": r["paper_title"],
                             "year": r["paper_year"]} for r in records}
    return {"formula": formula, "papers": list(papers.values()), "properties": records}


async def stats() -> dict:
    """兼容既有统计键；数量来自当前已批准的统一记录。"""
    async with async_session_factory() as session:
        counts = await database_counts(session)
    return {"subjects": counts["superconductors"], "triples": counts["records"]}

"""
sql_search.py — SQL 精确搜索模块。

支持 4 种搜索模式（按 example.md 设计）：
1. formula_search: 精确搜索化学式（LaH10）
2. elements_exact_search: 精确元素体系（La-H 只返回 H-La）
3. elements_combination_search: 元素子集组合
4. elements_contained_search: 包含搜索
"""

from __future__ import annotations

import json
import re
from typing import Any

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import func

from backend.models import (
    ChemicalSystem,
    MaterialState,
    Paper,
    PropertyRecord,
    Superconductor,
)

from backend.rag.search.property_records import (
    approved_materials_statement, approved_paper_conditions,
    format_property_record, property_records_statement,
)

_FORMULA_RE = re.compile(r"([A-Z][a-z]?)(\d*\.?\d*)")


def _normalize_formula(formula: str) -> str:
    """化学式归一化（元素字母排序），如 LaH10 → H10La，与重建脚本一致"""
    counts: dict[str, float] = {}
    for m in _FORMULA_RE.finditer(formula or ""):
        sym, n = m.group(1), m.group(2)
        counts[sym] = counts.get(sym, 0) + (float(n) if n else 1.0)
    parts = []
    for sym in sorted(counts):
        n = counts[sym]
        n_str = str(int(n)) if float(n).is_integer() else str(n)
        parts.append(f"{sym}{n_str if n != 1 else ''}")
    return "".join(parts)


async def search_by_formula(
    session: AsyncSession,
    formula: str,
) -> list[dict]:
    """按化学式精确搜索超导体。

    返回该超导体的所有物性记录（含 paper 信息）。
    """
    r = await session.execute(
        approved_materials_statement()
        .where(Superconductor.chemical_formula.ilike(formula))
    )
    superconductors = r.unique().scalars().all()

    if not superconductors:
        # 归一化后按 formula_normalized 匹配（chemical_formula 可能带相/掺杂注记，如 "LaH10 (fcc phase)"）
        normalized = _normalize_formula(formula)
        r = await session.execute(
            approved_materials_statement()
            .where(Superconductor.formula_normalized.ilike(normalized))
        )
        superconductors = r.unique().scalars().all()

    return await _format_superconductors(session, superconductors)


async def search_by_elements_exact(
    session: AsyncSession,
    elements: list[str],
) -> list[dict]:
    """精确搜索元素体系。

    输入 ['La', 'H']，只返回 system_key='H-La' 下的超导体。
    """
    sorted_elements = sorted(elements)
    system_key = "-".join(sorted_elements)

    r = await session.execute(
        approved_materials_statement()
        .join(ChemicalSystem)
        .where(ChemicalSystem.system_key == system_key)
    )
    superconductors = r.scalars().all()

    return await _format_superconductors(session, superconductors)


async def search_by_elements_combination(
    session: AsyncSession,
    elements: list[str],
) -> list[dict]:
    """元素子集组合搜索。

    输入 ['La', 'H', 'S']，返回 H-La、H-S、H-La-S 下的超导体。
    """
    sorted_input = sorted(elements)
    results = []

    # 生成所有非空子集
    from itertools import combinations
    for r_len in range(1, len(sorted_input) + 1):
        for subset in combinations(sorted_input, r_len):
            system_key = "-".join(subset)
            r = await session.execute(
                approved_materials_statement()
                .join(ChemicalSystem)
                .where(ChemicalSystem.system_key == system_key)
            )
            scs = r.scalars().all()
            results.extend(await _format_superconductors(session, scs))

    return results


async def search_by_elements_contained(
    session: AsyncSession,
    elements: list[str],
) -> list[dict]:
    """包含搜索。

    输入 ['La', 'H']，返回 H-La、H-La-S、H-La-O 等包含 La 和 H 的所有体系。
    """
    sorted_input = sorted(elements)
    # 找到所有 system_key 包含所有这些元素的体系
    # 在 SQLite 中用 LIKE 匹配
    from sqlalchemy import and_

    conditions = []
    for elem in sorted_input:
        # system_key 格式是 "H-La-S"，每个元素前后有 -
        conditions.append(or_(ChemicalSystem.system_key == elem,
                              ChemicalSystem.system_key.like(f"{elem}-%"),
                              ChemicalSystem.system_key.like(f"%-{elem}-%"),
                              ChemicalSystem.system_key.like(f"%-{elem}")))

    r = await session.execute(
        select(ChemicalSystem)
        .where(and_(*conditions))
        .where(ChemicalSystem.element_count >= len(sorted_input))
    )
    systems = r.scalars().all()

    results = []
    for sys in systems:
        r2 = await session.execute(
            approved_materials_statement()
            .where(Superconductor.chemical_system_id == sys.id)
        )
        scs = r2.scalars().all()
        results.extend(await _format_superconductors(session, scs))

    return results


async def search_papers(
    session: AsyncSession,
    keyword: str,
    limit: int = 20,
) -> list[dict]:
    """搜索论文（按标题、摘要、summary 关键词匹配）。"""
    pattern = f"%{keyword}%"
    r = await session.execute(
        select(Paper)
        .where(
            (Paper.title.ilike(pattern)
             | Paper.abstract.ilike(pattern)
             | Paper.summary.ilike(pattern)
             | Paper.authors.ilike(pattern))
            & and_(*approved_paper_conditions())
        )
        .limit(limit)
    )
    papers = r.scalars().all()

    return [
        {
            "type": "paper",
            "id": p.id,
            "doi": p.doi,
            "title": p.title,
            "authors": p.authors,
            "journal": p.journal,
            "year": p.year,
            "summary": p.summary,
            "paper_type": p.paper_type,
        }
        for p in papers
    ]


async def get_superconductor_records(
    session: AsyncSession,
    superconductor_id: int,
) -> list[dict]:
    """获取某个超导体的所有物性记录。"""
    rows = (await session.execute(
        property_records_statement().where(MaterialState.superconductor_id == superconductor_id)
        .order_by(PropertyRecord.id)
    )).all()
    return [format_property_record(*row) for row in rows]


async def get_paper_detail(session: AsyncSession, paper_id: int) -> dict | None:
    """获取论文详情（含当前材料状态的物性记录数）。"""
    r = await session.execute(
        select(Paper)
        .where(Paper.id == paper_id, *approved_paper_conditions())
    )
    paper = r.unique().scalar_one_or_none()
    if not paper:
        return None
    record_count = await session.scalar(
        select(func.count()).select_from(
            property_records_statement().where(PropertyRecord.paper_id == paper.id).subquery()
        )
    )

    return {
        "id": paper.id,
        "doi": paper.doi,
        "title": paper.title,
        "authors": paper.authors,
        "journal": paper.journal,
        "year": paper.year,
        "abstract": paper.abstract,
        "summary": paper.summary,
        "keywords_tags": json.loads(paper.keywords_tags) if paper.keywords_tags else [],
        "paper_type": paper.paper_type,
        "record_count": int(record_count or 0),
    }


async def _format_superconductors(session, superconductors) -> list[dict]:
    """批量加载物性，各搜索模式使用同一输出契约。"""
    if not superconductors:
        return []
    ids = [sc.id for sc in superconductors]
    rows = (await session.execute(
        property_records_statement().where(MaterialState.superconductor_id.in_(ids))
        .order_by(PropertyRecord.id)
    )).all()
    grouped = {sid: [] for sid in ids}
    for row in rows:
        item = format_property_record(*row)
        grouped[item["superconductor_id"]].append(item)
    return [
        {
            "type": "superconductor", "id": sc.id,
            "chemical_formula": sc.chemical_formula,
            "formula_normalized": sc.formula_normalized,
            "display_name": sc.display_name,
            "composition": _json_value(sc.composition, {}),
            "element_ratio": _json_value(sc.element_ratio, {}),
            "properties": grouped[sc.id],
        }
        for sc in superconductors
    ]


def _json_value(value, fallback):
    return json.loads(value) if isinstance(value, str) else value if value is not None else fallback

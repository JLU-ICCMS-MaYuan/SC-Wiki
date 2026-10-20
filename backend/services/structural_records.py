"""结构资料的统一校验、论文版本保存和读取。"""

from __future__ import annotations
import copy
import hashlib
import json
import math
from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from sqlalchemy import select, inspect, delete
from backend.structural_models import PaperStructuralRecord as Record
from backend.services.structure_candidates import read_atoms, export_representations, validate_atoms

VERSION = "structural-records-v1"


def fingerprint(value):
    return hashlib.sha256(
        json.dumps(jsonable_encoder(value), sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def available(session):
    return inspect(session.get_bind()).has_table(Record.__tablename__)


def number(value, *, positive=False):
    if value is None:
        return None
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or (positive and value <= 0)
    ):
        raise ValueError("结构资料包含无效数值")
    return value


def sources(raw):
    keys = {
        "file_id",
        "filename",
        "role",
        "page",
        "table",
        "row",
        "quote",
        "sha256",
        "bbox",
        "source_revision",
    }
    return [
        {k: copy.deepcopy(v) for k, v in item.items() if k in keys}
        for item in raw or []
        if isinstance(item, dict)
    ]


def normalize(item, kind):
    """不信任浏览器的哈希、元素、校验和派生表示。"""
    from pymatgen.core import Composition

    value = copy.deepcopy(item)
    retention = value.get("retention", "retained" if value.get("confirmation") == "confirmed" else "pending")
    if retention == "pending" and value.get("confirmation") == "confirmed":
        retention = "retained"
    if retention not in {"retained", "pending", "excluded"}:
        raise ValueError("结构资料保留决定无效")
    if kind == "model":
        text = ((value.get("representations") or {}).get("conventional", {}).get("cif") or {}).get("text")
        fmt = "cif"
        if not text:
            text, fmt = value.get("original_text"), value.get("original_format")
        atoms = read_atoms(fmt or "cif", text or "")
        reported = value.get("reported_structure") or {}
        actual = Composition(atoms.get_chemical_formula())
        material = str(reported.get("material") or actual.reduced_formula)
        if Composition(material).reduced_composition != actual.reduced_composition:
            raise ValueError("结构原子与报告化学式不一致")
        value.update(
            validation=validate_atoms(atoms, "cif").as_dict(), representations=export_representations(atoms)
        )
        pressure, group = reported.get("pressure_value_gpa"), reported.get("space_group_symbol")
        key = str(value.get("candidate_id") or "")
    else:
        material = str(value.get("material") or "")
        if not material:
            raise ValueError("晶格观测缺少材料化学式")
        cells = value.get("cell_parameters") or {}
        if not cells:
            raise ValueError("晶格观测没有几何参数")
        if any(k not in {"a", "b", "c", "alpha", "beta", "gamma", "volume"} for k in cells):
            raise ValueError("晶格参数名称无效")
        for v in cells.values():
            if number(v, positive=True) is None:
                raise ValueError("晶格参数不能是空值")
        if value.get("unit", "angstrom") != "angstrom":
            raise ValueError("晶格长度单位尚不支持，需保留原单位并核对")
        constraints = value.get("cell_constraints") or {}
        if constraints and constraints != {"b": "a"}:
            raise ValueError("晶格约束形式尚不支持")
        derived = {"b": cells["a"]} if constraints == {"b": "a"} and "a" in cells else {}
        group = value.get("space_group_symbol")
        if group:
            from pymatgen.symmetry.groups import SpaceGroup

            if SpaceGroup(group).crystal_system == "hexagonal":
                derived.update(
                    {k: v for k, v in {"alpha": 90, "beta": 90, "gamma": 120}.items() if k not in cells}
                )
        value["derived_cell_parameters"] = derived
        for bond in value.get("bond_lengths") or []:
            if bond.get("unit", "angstrom") != "angstrom":
                raise ValueError("键长单位尚不支持")
            low, high = number(bond.get("min"), positive=True), number(bond.get("max"), positive=True)
            if low is None or high is None or low > high:
                raise ValueError("键长范围无效")
        value["coordinate_status"] = "not_reported"
        pressure, group, key = (
            value.get("pressure_value_gpa"),
            value.get("space_group_symbol"),
            str(value.get("record_key") or ""),
        )
    if not key or len(key) > 128:
        raise ValueError("结构资料缺少稳定来源标识")
    value["sources"] = sources(value.get("sources"))
    value["retention"] = retention
    if retention == "retained" and not any(
        (s.get("file_id") or s.get("filename"))
        and (
            s.get("quote")
            or kind == "model"
            and value.get("source_kind") == "attachment"
            and value.get("original_text")
        )
        for s in value["sources"]
    ):
        raise ValueError("保留资料须提供可核对的来源")
    elements = sorted(str(e) for e in Composition(material).elements)
    if len(material) > 255 or (group and len(str(group)) > 100):
        raise ValueError("结构资料名称过长")
    return dict(
        record_key=key,
        kind=kind,
        material=material,
        elements=elements,
        system_key="-".join(elements),
        pressure_gpa=number(pressure),
        space_group=group,
        retention=retention,
        data_json=jsonable_encoder(value),
    )


def draft_items(draft):
    result = []
    for candidate in draft.get("structure_candidates") or []:
        if "retention" in candidate:
            # 真正的失败项仍留在草稿供核对，不以有效模型形式落库。
            if candidate.get("status") == "blocked":
                reported = candidate.get("reported_structure") or {}
                result.append(
                    dict(
                        record_key=str(
                            candidate.get("candidate_id") or "issue:" + fingerprint(candidate)[:32]
                        ),
                        kind="issue",
                        material=str(reported.get("material") or ""),
                        elements=[],
                        system_key="",
                        retention="pending",
                        pressure_gpa=number(reported.get("pressure_value_gpa")),
                        space_group=reported.get("space_group_symbol"),
                        data_json={
                            **copy.deepcopy(candidate),
                            "sources": sources(candidate.get("sources")),
                            "retention": "pending",
                        },
                    )
                )
                continue
            original = copy.deepcopy(candidate.get("structural_record") or candidate)
            original["retention"] = candidate["retention"]
            data = normalize(original, "model")
            ref = str(candidate.get("material_state_ref") or "")
            if ref.startswith("material_states["):
                try:
                    index = int(ref.split("[")[1].split("]")[0])
                    state = draft["material_states"][index]
                    data["state_key"] = state.get("state_key") or f"state-{index + 1}"
                except (ValueError, IndexError, KeyError):
                    data["state_key"] = None
            result.append(data)
    result.extend(normalize(item, "lattice") for item in draft.get("structural_observations") or [])
    for problem in draft.get("structural_extraction_issues") or []:
        key = problem.get("record_key") or "issue:" + fingerprint(problem)[:32]
        result.append(
            dict(
                record_key=key,
                kind="issue",
                material="",
                elements=[],
                system_key="",
                retention="pending",
                data_json={**copy.deepcopy(problem), "record_key": key, "sources": sources([problem])},
            )
        )
    keys = [r["record_key"] for r in result]
    if any(not isinstance(key, str) or not key or len(key) > 128 for key in keys):
        raise ValueError("结构资料来源标识无效")
    if len(keys) != len(set(keys)):
        raise ValueError("结构资料来源标识重复")
    return result


def validate_draft(draft):
    if (
        not any("retention" in item for item in draft.get("structure_candidates") or [])
        and not draft.get("structural_observations")
        and not draft.get("structural_extraction_issues")
    ):
        return
    try:
        draft_items(draft)
    except (ValueError, TypeError, AttributeError) as exc:
        raise HTTPException(400, detail={"code": "invalid_structural_record", "message": str(exc)}) from exc


async def persist(session, paper, draft, source_file_ids=None):
    items = draft_items(draft)
    if not items and "structural_observations" not in draft:
        return
    if not await session.run_sync(available):
        if items:
            raise HTTPException(
                503,
                detail={
                    "code": "structural_migration_required",
                    "message": "结构资料存储尚未升级，请先应用 #49 迁移",
                },
            )
        return
    await session.execute(
        delete(Record).where(Record.paper_id == paper.id, Record.paper_revision == paper.content_revision)
    )
    for item in items:
        for source in item["data_json"]["sources"]:
            if str(source.get("file_id")) in (source_file_ids or {}):
                source["file_id"] = str(source_file_ids[str(source["file_id"])])
        session.add(Record(paper_id=paper.id, paper_revision=paper.content_revision, **item))
    await session.flush()


def current_items(session, paper):
    if not available(session):
        return []
    return list(
        session.scalars(
            select(Record)
            .where(Record.paper_id == paper.id, Record.paper_revision == paper.content_revision)
            .order_by(Record.record_key)
        )
    )


def supplement_draft(session, paper, draft):
    items = current_items(session, paper)
    if not items:
        return draft
    draft["structural_observations"] = []
    adopted_states = {s.get("state_key") or f"state-{i+1}": i for i, s in enumerate(draft["material_states"])}
    for row in items:
        value = copy.deepcopy(row.data_json)
        value["retention"] = row.retention
        if row.kind == "lattice":
            draft["structural_observations"].append(value)
        elif row.kind == "issue" and not value.get("candidate_id"):
            draft.setdefault("structural_extraction_issues", []).append(value)
        else:
            if any(
                c.get("candidate_id") == value.get("candidate_id")
                for c in draft.get("structure_candidates") or []
            ):
                continue
            # 已采用规范几何由原读取链提供；论文独立资料仍可经资料接口完整读取。
            if row.state_key in adopted_states:
                adopted = next(
                    (
                        c
                        for c in draft.get("structure_candidates") or []
                        if c.get("material_state_ref") == f"material_states[{adopted_states[row.state_key]}]"
                    ),
                    None,
                )
                if adopted:
                    adopted.update(retention=row.retention, structural_record=value)
                    continue
            value["material_state_ref"] = (
                f"material_states[{adopted_states[row.state_key]}]"
                if row.state_key in adopted_states
                else "unassigned:paper"
            )
            draft.setdefault("structure_candidates", []).append(value)
    draft["structural_extraction_version"] = VERSION
    return draft


def serialize(row, paper, *, private=False):
    value = copy.deepcopy(row.data_json)
    if not private:
        public_fields = {
            "candidate_id",
            "record_key",
            "material_state_ref",
            "source_kind",
            "status",
            "confirmation",
            "retention",
            "original_format",
            "original_text",
            "validation",
            "derivation",
            "reported_structure",
            "representations",
            "sources",
            "material",
            "pressure_value_gpa",
            "space_group_symbol",
            "calculation_label",
            "cell_parameters",
            "cell_constraints",
            "derived_cell_parameters",
            "coordinate_status",
            "unit",
            "bond_lengths",
            "extraction_version",
        }
        value = {key: data for key, data in value.items() if key in public_fields}
    return dict(
        id=row.id,
        kind=row.kind,
        material=row.material,
        elements=row.elements,
        pressure_gpa=float(row.pressure_gpa) if row.pressure_gpa is not None else None,
        space_group=row.space_group,
        retention=row.retention,
        state_key=row.state_key,
        data=value,
        paper_id=paper.id,
        paper_revision=row.paper_revision,
        title=paper.title,
        doi=paper.doi,
        year=paper.year,
    )

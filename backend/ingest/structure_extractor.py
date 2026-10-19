"""Extract deterministic crystal-structure candidates from searchable PDF text.

This parser intentionally handles only explicit lattice and coordinate tables. It
does not infer missing cells, coordinate systems, occupancies, or disorder.
"""

from __future__ import annotations

import re
import hashlib
from pathlib import Path
from typing import Any

from ase import Atoms

from backend.services.structure_candidates import (
    StructureCandidateError,
    build_structure_candidate,
    serialize_atoms,
)


_NUMBER = r"[-+]?\d+(?:\.\d+)?"
_ELEMENT = r"[A-Z][a-z]?"
_PAGE = re.compile(r"<!--\s*page:\s*(\d+)\s*-->")
_CELL_KEYS = {
    "a": ("_cell_length_a", "cell_length_a"),
    "b": ("_cell_length_b", "cell_length_b"),
    "c": ("_cell_length_c", "cell_length_c"),
    "alpha": ("_cell_angle_alpha", "cell_angle_alpha"),
    "beta": ("_cell_angle_beta", "cell_angle_beta"),
    "gamma": ("_cell_angle_gamma", "cell_angle_gamma"),
}
_GREEK_CELL_NAMES = str.maketrans({"α": "alpha", "β": "beta", "γ": "gamma",
                                 "\uf061": "alpha", "\uf062": "beta", "\uf067": "gamma"})
_SITE_LABEL = re.compile(rf"({_ELEMENT})\s*\((\d+[a-z])\)")
_SITE_ROW = re.compile(rf"({_ELEMENT})\s*\((\d+[a-z])\)\s+({_NUMBER})\s+({_NUMBER})\s+({_NUMBER})")


def _page_for_offset(text: str, offset: int) -> int | None:
    markers = list(_PAGE.finditer(text, 0, offset))
    return int(markers[-1].group(1)) if markers else None


def _cell_parameters(text: str) -> dict[str, float]:
    text = text.translate(_GREEK_CELL_NAMES)
    values: dict[str, float] = {}
    for key, aliases in _CELL_KEYS.items():
        alias_pattern = "|".join(re.escape(alias) for alias in aliases)
        match = re.search(rf"(?:{alias_pattern})\s*[=:]?\s*({_NUMBER})", text, re.IGNORECASE)
        if match:
            values[key] = float(match.group(1))
    # Common prose form: a = 3.5 Å, b = 3.5 Å ...
    for key in ("a", "b", "c", "alpha", "beta", "gamma"):
        if key in values:
            continue
        match = re.search(rf"\b{key}\s*[=:]\s*({_NUMBER})", text, re.IGNORECASE)
        if match:
            values[key] = float(match.group(1))
    return values


def _coordinate_mode(text: str) -> str | None:
    lowered = text.lower()
    if re.search(r"fractional|frac(?:tional)?\s+coordinates?|crystallographic", lowered):
        return "fractional"
    if re.search(r"cartesian|cart\.?\s+coordinates?", lowered):
        return "cartesian"
    return None


def _coordinate_rows(text: str, mode: str) -> tuple[list[str], list[tuple[float, float, float]], str] :
    symbols: list[str] = []
    positions: list[tuple[float, float, float]] = []
    rows: list[str] = []
    pattern = re.compile(
        rf"^\s*(?:\d+\s+)?({_ELEMENT})(?:\d+|[A-Za-z]{{0,3}})?\s+(?:({_ELEMENT})\s+)?"
        rf"({_NUMBER})\s+({_NUMBER})\s+({_NUMBER})(?:\s|$)"
    )
    for line in text.splitlines():
        match = pattern.match(line)
        if not match:
            continue
        symbol = match.group(2) or match.group(1)
        symbols.append(symbol)
        positions.append(tuple(float(match.group(index)) for index in (3, 4, 5)))
        rows.append(line.strip())
    return symbols, positions, "\n".join(rows)


def _wyckoff_structure(text: str, cells: dict[str, float]):
    if not re.search(r"wyckoff", text, re.IGNORECASE):
        return None
    number_match = re.search(r"(?:space\s*group|international\s+number|no\.?)[^\n]{0,80}?\b(\d{1,3})\b", text, re.IGNORECASE)
    symbol_match = re.search(r"(?:space\s*group|Hermann[- ]Mauguin)[^\n:=]{0,20}[:=]?\s*([PIFRAC][^\n,(;]{1,18})", text, re.IGNORECASE)
    if not number_match and not symbol_match:
        return None
    try:
        from pymatgen.core import Lattice, Structure
        from pymatgen.symmetry.groups import SpaceGroup

        if number_match:
            group = SpaceGroup.from_int_number(int(number_match.group(1)))
        else:
            group = SpaceGroup(symbol_match.group(1).strip())
    except Exception:
        return None
    species: list[str] = []
    coords: list[list[float]] = []
    independent_rows: list[str] = []
    row_pattern = re.compile(
        rf"^\s*(?:(?:\d+)?[A-Za-z]\s+)?({_ELEMENT})\s+(?:(?:\d+)?[A-Za-z]\s+)?"
        rf"({_NUMBER})\s+({_NUMBER})\s+({_NUMBER})(?:\s|$)"
    )
    for line in text.splitlines():
        if not re.search(r"\b\d*[a-zA-Z]\b", line):
            continue
        match = row_pattern.match(line)
        if not match:
            continue
        species.append(match.group(1))
        coords.append([float(match.group(index)) for index in (2, 3, 4)])
        independent_rows.append(line.strip())
    if not species:
        return None
    lattice = Lattice.from_parameters(
        cells["a"], cells["b"], cells["c"],
        cells["alpha"], cells["beta"], cells["gamma"],
    )
    structure = Structure.from_spacegroup(group.symbol, lattice, species, coords)
    return structure, group.symbol, independent_rows


def _blocked_candidate(source: dict[str, Any], reason: str, *, page: int | None, quote: str,
                       cell_parameters: dict[str, float] | None = None) -> dict[str, Any]:
    file_id = source.get("file_id") or source.get("filename") or "pdf"
    return {
        "candidate_id": f"blocked:pdf:{file_id}:{page or 0}",
        "material_state_ref": f"unassigned:{file_id}",
        "source_kind": "pdf_reported",
        "status": "blocked",
        "confirmation": "unreviewed",
        "original_format": None,
        "original_text": None,
        "validation": {"ase_valid": False, "code": "pdf_structure_incomplete", "message": reason},
        "derivation": None,
        "representations": {},
        "sources": [{**source, "page": page, "quote": quote}],
        "reported_structure": {"cell_parameters": cell_parameters} if cell_parameters else None,
        "conflicts": [],
        "user_note": None,
    }


def _extract_structure_candidate_block(
    markdown: str,
    *,
    source: dict[str, Any],
    material_state_ref: str | None = None,
) -> list[dict[str, Any]]:
    """Extract explicit coordinate-table candidates while preserving page evidence."""
    text = str(markdown or "")
    if not text.strip():
        return []
    # 提到空间群或晶格常数并不表示该页报告了原子结构。
    cues = re.search(r"atomic\s+coordinates?|fractional\s+coordinates?|cartesian\s+coordinates?|wyckoff|_atom_site_", text, re.IGNORECASE)
    if not cues:
        return []
    cells = _cell_parameters(text)
    mode = _coordinate_mode(text)
    if len(cells) < 6:
        return [_blocked_candidate(source, "PDF 结构缺少完整晶胞参数（a、b、c、alpha、beta、gamma）", page=_page_for_offset(text, cues.start()), quote=text[max(0, cues.start() - 160):cues.end() + 320], cell_parameters=cells)]
    wyckoff = _wyckoff_structure(text, cells)
    if wyckoff is not None:
        structure, group_symbol, independent_rows = wyckoff
        try:
            from pymatgen.io.ase import AseAtomsAdaptor

            atoms = AseAtomsAdaptor.get_atoms(structure)
            source_with_locator = {**source, "page": _page_for_offset(text, cues.start()), "quote": "\n".join(independent_rows)}
            candidate = build_structure_candidate(
                structure_format="cif",
                structure_text=serialize_atoms(atoms, "cif"),
                source=source_with_locator,
                material_state_ref=material_state_ref or f"unassigned:{source.get('file_id') or 'pdf'}",
                source_kind="pdf_derived",
            )
            candidate["original_format"] = None
            candidate["original_text"] = None
            candidate["reported_structure"] = {"space_group_symbol": group_symbol, "cell_parameters": cells}
            candidate["derivation"] = {
                "kind": "space_group_expansion",
                "label": "推导",
                "space_group_symbol": group_symbol,
                "independent_wyckoff_rows": independent_rows,
            }
            return [candidate]
        except Exception:
            return [_blocked_candidate(source, "Wyckoff 位点展开失败，需人工核对空间群和独立坐标", page=_page_for_offset(text, cues.start()), quote="\n".join(independent_rows), cell_parameters=cells)]
    if mode is None:
        return [_blocked_candidate(source, "PDF 原子坐标类型不明确，无法区分分数坐标和笛卡尔坐标", page=_page_for_offset(text, cues.start()), quote=text[max(0, cues.start() - 160):cues.end() + 320], cell_parameters=cells)]
    symbols, positions, quote = _coordinate_rows(text, mode)
    if not symbols:
        return [_blocked_candidate(source, "PDF 未找到完整原子坐标行，不能仅凭空间群生成结构", page=_page_for_offset(text, cues.start()), quote=text[max(0, cues.start() - 160):cues.end() + 320], cell_parameters=cells)]
    cell = [cells[key] for key in ("a", "b", "c", "alpha", "beta", "gamma")]
    atoms = Atoms(symbols=symbols, positions=positions if mode == "cartesian" else None,
                  scaled_positions=positions if mode == "fractional" else None,
                  cell=cell, pbc=True)
    try:
        original = build_structure_candidate(
            structure_format="cif",
            structure_text=serialize_atoms(atoms, "cif"),
            source={**source, "page": _page_for_offset(text, cues.start()), "quote": quote},
            material_state_ref=material_state_ref or f"unassigned:{source.get('file_id') or 'pdf'}",
            source_kind="pdf_reported",
        )
    except StructureCandidateError as exc:
        return [_blocked_candidate(source, str(exc), page=_page_for_offset(text, cues.start()), quote=quote, cell_parameters=cells)]
    original["original_format"] = None
    original["original_text"] = None
    original["reported_structure"] = {"coordinate_mode": mode, "cell_parameters": cells, "coordinate_rows": quote}
    original["derivation"] = {"kind": "direct_coordinates", "label": "原文直接报告"}
    return [original]


def _phase_table_candidates(markdown: str, source: dict[str, Any]) -> tuple[list[dict[str, Any]], set[int]]:
    """按物相拆分带 Wyckoff 位点的结构表，避免把多相晶胞拼成一个模型。"""
    table = re.search(r"(?im)^Table\s+S?\d+\s*[.|:]\s*[^\n]*?structur(?:e|al)\s+parameters\b", markdown)
    if not table:
        return [], set()
    start_page = list(_PAGE.finditer(markdown, 0, table.start()))
    table_start = start_page[-1].start() if start_page else table.start()
    end = re.search(r"(?im)^(?:Table|Figure|Fig\.)\s+S?\d+\s*[.|:]", markdown[table.end():])
    table_end = table.end() + end.start() if end else len(markdown)
    text = markdown[table_start:table_end]
    # Docling 会把单元格逐个换行，并在其间加入 block 注释；等长空白替换保留页码偏移。
    text = re.sub(r"<!--\s*block:[^>]*-->", lambda match: " " * len(match.group()), text)
    if not re.search(r"Atomic coordinates\s*\(fractional\)", text, re.IGNORECASE):
        return [], set()
    heads = list(re.finditer(rf"(?m)^\s*(?:(?P<material>[A-Z][A-Za-z0-9]{{0,30}})\s+)?(?P<symbol>[A-Z][A-Za-z0-9/-]{{0,12}})\s+a\s*=\s*({_NUMBER})\b", text))
    if not heads:
        return [], set()
    candidates: list[dict[str, Any]] = []
    pages: set[int] = set()
    header_pressure = re.search(r"(?:at|under)\s+(\d+(?:\.\d+)?)\s*GPa", text[:heads[0].start()], re.IGNORECASE)
    phase_parts: dict[tuple, dict[str, Any]] = {}
    for index, head in enumerate(heads):
        symbol, material = head.group("symbol"), head.group("material")
        segment = text[head.start():heads[index + 1].start() if index + 1 < len(heads) else len(text)]
        page = _page_for_offset(markdown, table_start + head.start())
        if page:
            pages.add(page)
        normalized = segment.translate(_GREEK_CELL_NAMES)
        cells = _cell_parameters(normalized)
        pressure_match = re.search(r"\((\d+(?:\.\d+)?)\s*GPa\)", normalized[:160], re.IGNORECASE)
        pressure = float(pressure_match.group(1)) if pressure_match else float(header_pressure.group(1)) if header_pressure else None
        unique_rows = {tuple(row.group(part) for part in (1, 2, 3, 4, 5)): row
                       for row in _SITE_ROW.finditer(normalized)}
        valid_rows = [(row, [float(row.group(part)) for part in (3, 4, 5)])
                      for row in unique_rows.values()]
        missing_rows = len(_SITE_LABEL.findall(normalized)) != len(list(_SITE_ROW.finditer(normalized)))
        invalid_sites = 0
        rounding_adjustments = []
        try:
            from pymatgen.symmetry.groups import SpaceGroup
            from backend.services.wyckoff_rounding import restore_rounded_site
            group_for_sites = SpaceGroup(symbol)
            valid_rows = []
            for row in unique_rows.values():
                multiplicity = int(re.match(r"\d+", row.group(2)).group())
                try:
                    coords, adjustment = restore_rounded_site(group_for_sites, [row.group(i) for i in (3, 4, 5)], multiplicity)
                except ValueError:
                    invalid_sites += 1
                    continue
                if adjustment:
                    rounding_adjustments.append({"site": f"{row.group(1)}({row.group(2)})", **adjustment})
                valid_rows.append((row, coords))
        except Exception:
            invalid_sites = len(unique_rows)
        identity = (material, symbol, pressure, tuple(sorted(cells.items())))
        # 跨页重复表头可省略压力；只与唯一的同几何、同材料条件合并。
        compatible = [key for key in phase_parts if key[:2] == identity[:2] and key[3] == identity[3]
                      and (key[2] == pressure or key[2] is None or pressure is None)]
        if len(compatible) == 1:
            identity = compatible[0]
        part = phase_parts.get(identity)
        if part is None:
            phase_parts[identity] = {"symbol": symbol, "material": material, "segment": segment, "page": page,
                                     "cells": cells, "pressure": pressure, "rows": valid_rows,
                                     "missing_rows": missing_rows,
                                     "rounding_adjustments": rounding_adjustments,
                                     "invalid_sites": invalid_sites,
                                     "pressure_source": {**source, "page": page if pressure_match else _page_for_offset(markdown, table.start()),
                                                         "quote": segment.strip() if pressure_match else text[:heads[0].start()].strip()} if pressure is not None else None}
        else:
            if pressure is not None:
                part["pressure"] = pressure
                part["pressure_source"] = {**source, "page": page, "quote": segment.strip()}
            if (invalid_sites == 0, len(valid_rows)) > (part["invalid_sites"] == 0, len(part["rows"])):
                part.update(segment=segment, page=page, rows=valid_rows, invalid_sites=invalid_sites,
                            missing_rows=missing_rows, rounding_adjustments=rounding_adjustments)
    for part in phase_parts.values():
        symbol, segment, page = part["symbol"], part["segment"], part["page"]
        cells, pressure, rows = dict(part["cells"]), part["pressure"], part["rows"]
        source_with_quote = {**source, "page": page, "quote": segment.strip()}
        condition_id = hashlib.sha256(repr((part["material"], symbol, pressure, sorted(cells.items()))).encode()).hexdigest()[:16]
        try:
            from pymatgen.core import Lattice, Structure
            from pymatgen.symmetry.groups import SpaceGroup
            from pymatgen.io.ase import AseAtomsAdaptor

            group = SpaceGroup(symbol)
            inferred: list[str] = []
            system = group.crystal_system
            if system == "cubic" and "a" in cells:
                for key in ("b", "c"):
                    if key not in cells:
                        cells[key] = cells["a"]; inferred.append(key)
            elif system in {"tetragonal", "hexagonal", "trigonal"} and "a" in cells and "b" not in cells:
                cells["b"] = cells["a"]; inferred.append("b")
            if system == "orthorhombic" or system == "cubic" or system == "tetragonal":
                angles = {"alpha": 90, "beta": 90, "gamma": 90}
            elif system in {"hexagonal", "trigonal"} and symbol.startswith("R"):
                angles = {"alpha": 90, "beta": 90, "gamma": 120}
            else:
                angles = {}
            for key, value in angles.items():
                if key not in cells:
                    cells[key] = value; inferred.append(key)
            required = {"a", "b", "c", "alpha", "beta", "gamma"}
            if not required.issubset(cells):
                raise ValueError("缺少可验证的晶胞参数")
            if part["missing_rows"]:
                raise ValueError("原子标签与坐标列已拆散，无法可靠恢复逐行对应关系")
            if part["invalid_sites"]:
                raise ValueError("位点多重性与报告空间群不一致，需核对原文坐标精度或舍入")
            if not rows:
                raise ValueError("缺少可验证的原子位点")
            species = [row.group(1) for row, _ in rows]
            coords = [point for _, point in rows]
            lattice = Lattice.from_parameters(*(cells[key] for key in ("a", "b", "c", "alpha", "beta", "gamma")))
            structure = Structure.from_spacegroup(group.symbol, lattice, species, coords)
            if len(structure) != sum(int(re.match(r"\d+", row.group(2)).group()) for row, _ in rows):
                raise ValueError("展开原子数与报告的位点多重性之和不一致")
            if part["material"]:
                from pymatgen.core import Composition
                if structure.composition.reduced_composition != Composition(part["material"]).reduced_composition:
                    raise ValueError("展开后的化学计量与表中化学式不一致")
            atoms = AseAtomsAdaptor.get_atoms(structure)
            candidate = build_structure_candidate(
                structure_format="cif", structure_text=serialize_atoms(atoms, "cif"),
                source=source_with_quote, material_state_ref=f"unassigned:{source.get('file_id') or 'pdf'}",
                source_kind="pdf_derived" if group.int_number != 1 or inferred else "pdf_reported",
            )
            candidate["original_format"] = None
            candidate["original_text"] = None
            candidate["candidate_id"] += ":" + condition_id
            candidate["reported_structure"] = {"space_group_symbol": symbol, "cell_parameters": cells,
                                               "material": part["material"], "pressure_value_gpa": pressure, "independent_sites": len(rows)}
            candidate["derivation"] = {"kind": "space_group_expansion" if group.int_number != 1 else "direct_coordinates",
                                        "label": "按原文精度恢复对称约束后展开" if part["rounding_adjustments"] else "空间群展开" if group.int_number != 1 else "原文直接报告",
                                        "inferred_cell_parameters": inferred,
                                        "rounding_adjustments": part["rounding_adjustments"],
                                        "rounded_fractional_sites": [f"{row.group(1)}({row.group(2)})" for row, point in rows
                                                                     if point != [float(row.group(i)) for i in (3, 4, 5)]]}
            if part["pressure_source"] and part["pressure_source"]["quote"] != source_with_quote["quote"]:
                candidate["sources"].append(part["pressure_source"])
            candidates.append(candidate)
        except Exception as exc:
            blocked = _blocked_candidate(source, f"结构表 {symbol} 无法生成可靠模型：{exc}",
                                         page=page, quote=segment.strip(), cell_parameters=cells)
            blocked["reported_structure"] = {"space_group_symbol": symbol, "cell_parameters": cells,
                                             "material": part["material"], "pressure_value_gpa": pressure}
            blocked["candidate_id"] += ":" + condition_id
            candidates.append(blocked)
    return candidates, pages


def extract_structure_candidates(
    markdown: str,
    *,
    source: dict[str, Any],
    material_state_ref: str | None = None,
    pdf_path: Path | None = None,
) -> list[dict[str, Any]]:
    """Extract one candidate per explicit page block to avoid merging conditions."""
    text = str(markdown or "")
    if not text.strip():
        return []
    if pdf_path is not None:
        # 仅在坐标表页取原 PDF 的行布局；不从已丢列关系的 Markdown 猜测坐标。
        import pymupdf
        with pymupdf.open(pdf_path) as document:
            for index, page in enumerate(document):
                rows = page.get_text(sort=True)
                if not re.search(r"Atomic\s+coordinates\s*\(fractional\)", rows, re.IGNORECASE):
                    continue
                marker = f"<!-- page: {index + 1} -->"
                pattern = rf"{re.escape(marker)}.*?(?=<!--\s*page:\s*\d+\s*-->|\Z)"
                block = re.search(pattern, text, flags=re.DOTALL)
                if block and _SITE_LABEL.search(block.group()) and len(_SITE_LABEL.findall(block.group())) == len(_SITE_ROW.findall(block.group())):
                    continue
                text = re.sub(pattern, lambda _: marker + "\n" + rows + "\n", text, flags=re.DOTALL)
    blocks = re.split(r"(?=<!--\s*page:\s*\d+\s*-->)", text, flags=re.IGNORECASE)
    if len(blocks) == 1:
        blocks = [text]
    candidates, table_pages = _phase_table_candidates(text, source)
    for block in blocks:
        page_match = _PAGE.search(block)
        if page_match and int(page_match.group(1)) in table_pages:
            continue
        candidates.extend(_extract_structure_candidate_block(
            block,
            source=source,
            material_state_ref=material_state_ref,
        ))
    return candidates

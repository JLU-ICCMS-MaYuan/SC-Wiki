"""从可搜索 PDF 晶格表读取逐行观测；没有原子位置时不生成模型。"""

from __future__ import annotations
import re
from pathlib import Path
from backend.services.structural_records import fingerprint

N = r"\d+(?:\.\d+)?"


def _lines(words):
    rows = []
    for word in sorted(words, key=lambda w: ((w[1] + w[3]) / 2, w[0])):
        center = (word[1] + word[3]) / 2
        row = next((r for r in rows[-3:] if abs(r[0] - center) < 2), None)
        if row is None:
            row = [center, []]
            rows.append(row)
        row[1].append(word)
    return [(y, sorted(row, key=lambda w: w[0])) for y, row in rows]


def _rules(page):
    segments = []
    for drawing in page.get_drawings():
        for item in drawing["items"]:
            if item[0] == "re" and item[1].height <= 2:
                r = item[1]
                segments.append((r.y0, r.x0, r.x1))
            elif item[0] == "l" and abs(item[1].y - item[2].y) < 0.5:
                a, b = item[1:3]
                segments.append((a.y, min(a.x, b.x), max(a.x, b.x)))
    merged = []
    for y, x0, x1 in sorted(segments):
        same = next((r for r in merged if abs(r[0] - y) < 1.5 and x0 <= r[2] + 2 and x1 >= r[1] - 2), None)
        if same:
            same[1], same[2] = min(same[1], x0), max(same[2], x1)
        else:
            merged.append([y, x0, x1])
    return merged


def extract_lattice_observations(pdf_path: Path, *, source: dict):
    import pymupdf
    from pymatgen.core import Composition
    from pymatgen.symmetry.groups import SpaceGroup

    records, issues = [], []
    with pymupdf.open(pdf_path) as document:
        for index, page in enumerate(document):
            text = page.get_text(sort=True).replace("\u00ad", "")
            caption = re.search(
                r"Table\s+(S?\d+)[.|:]\s*(.*?)(?=\n\s*\n|\n[^\n]*(?:Calculation|Pressure\s*\(|Lattice\s+Parameters\s*\()|\Z)",
                text,
                re.I | re.S,
            )
            if not caption or not re.search(
                r"(?:structur(?:e|al)|lattice)\s+parameters", caption.group(), re.I
            ):
                continue
            if re.search(r"(?:atomic|fractional)\s+coordinates", text, re.I):
                continue
            location = {**source, "page": index + 1, "table": "Table " + caption.group(1)}
            try:
                identity = re.search(
                    r"\b([PIFRAC][A-Za-z0-9/\-]+)[\s\-]+([A-Z][A-Za-z0-9]+)", caption.group()
                )
                if identity is None:
                    raise ValueError("晶格表材料或空间群无法唯一识别")
                group, material = identity.groups()
                group = group.rstrip("-")
                crystal = SpaceGroup(group)
                Composition(material)
                if not re.search(r"Pressure\s*\(GPa\)", text, re.I) or not re.search(
                    r"Parameters\s*\(Å\)", text, re.I
                ):
                    raise ValueError("晶格表压力或长度单位尚不能确认")
                equal_ab = bool(re.search(r"\ba\s*=\s*b\s+c\b", text))
                independent_abc = bool(re.search(r"\ba\s+b\s+c\b", text))
                if not equal_ab and not independent_abc:
                    raise ValueError("晶格表列布局尚不支持，需核对原页")
                words = page.get_text("words")
                header = next(w for w in words if w[4] == "Pressure")
                labels = [
                    w
                    for w in words
                    if w[4].lower() in {"harmonic", "anharmonic"} and w[0] < header[0] and w[1] > header[1]
                ]
                rules, groups = _rules(page), []
                for label in labels:
                    x, y = (label[0] + label[2]) / 2, (label[1] + label[3]) / 2
                    borders = [r[0] for r in rules if r[1] <= x and r[2] >= header[2]]
                    top, bottom = max((v for v in borders if v < y), default=None), min(
                        (v for v in borders if v > y), default=None
                    )
                    if top is not None and bottom is not None:
                        groups.append((top, bottom, label[4]))
                count = 0
                for y, line in _lines(words):
                    if y <= header[3]:
                        continue
                    quote = " ".join(w[4] for w in line if w[0] >= header[0] - 5)
                    pattern = (
                        rf"({N})\s+({N})\s+({N})"
                        + (rf"\s+({N})" if independent_abc else "")
                        + rf"(?:\s+({N})\s*[-–]\s*({N}))?"
                    )
                    columns = re.fullmatch(pattern, quote)
                    if columns is None:
                        continue
                    values = columns.groups()
                    pressure = float(values[0])
                    cells = (
                        {"a": float(values[1]), "c": float(values[2])}
                        if equal_ab
                        else dict(zip(("a", "b", "c"), map(float, values[1:4])))
                    )
                    matches = [label for top, bottom, label in groups if top < y < bottom]
                    label = matches[0] if len(matches) == 1 else None
                    if labels and label is None:
                        issues.append(
                            {**location, "reason": "近似分组边界不能确认，保留观测待核对", "quote": quote}
                        )
                    count += 1
                    bounds = [
                        min(w[0] for w in line),
                        min(w[1] for w in line),
                        max(w[2] for w in line),
                        max(w[3] for w in line),
                    ]
                    derived = {"b": cells["a"]} if equal_ab else {}
                    if crystal.crystal_system == "hexagonal":
                        derived.update(alpha=90, beta=90, gamma=120)
                    low, high = values[-2:]
                    records.append(
                        dict(
                            record_key="lattice:"
                            + fingerprint(
                                [
                                    source.get("sha256") or source.get("file_id"),
                                    index + 1,
                                    caption.group(1),
                                    count,
                                    quote,
                                    label,
                                ]
                            )[:32],
                            material=material,
                            space_group_symbol=group,
                            pressure_value_gpa=pressure,
                            calculation_label=label,
                            cell_parameters=cells,
                            cell_constraints={"b": "a"} if equal_ab else {},
                            derived_cell_parameters=derived,
                            coordinate_status="not_reported",
                            unit="angstrom",
                            retention="pending",
                            bond_lengths=(
                                [dict(pair="H-H", min=float(low), max=float(high), unit="angstrom")]
                                if low is not None and "H-H" in text
                                else []
                            ),
                            sources=[
                                {**location, "quote": caption.group()},
                                {**location, "row": count, "bbox": bounds, "quote": quote},
                            ],
                            extraction_version="structural-records-v1",
                        )
                    )
                if not count:
                    raise ValueError("晶格表存在但没有可靠恢复数值行，需核对列关系")
            except (ValueError, StopIteration) as exc:
                issues.append({**location, "reason": str(exc) or "晶格表定位信息不完整"})
    return records, issues

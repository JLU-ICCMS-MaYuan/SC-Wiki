"""每材料状态的当前 DOS 与只读报告来源；不推断单位或选择冲突值。"""
from __future__ import annotations

from copy import deepcopy
import json

ARCHIVE_KEY = "dos_fermi_sources"
VALUE_FIELDS = ("value_number", "value_min", "value_max", "value_text", "value_boolean")
SCIENCE_FIELDS = ("record_type", "property_code", "definition_key", "definition_version", "name_raw",
                  "value_kind", "value_raw", *VALUE_FIELDS, "uncertainty", "unit_raw", "canonical_unit",
                  "method_code", "method_raw", "criterion_code", "criterion_raw", "structure_key")


def is_fermi_dos(record: dict) -> bool:
    return (record.get("module_code") == "electronic_properties"
            and record.get("record_type") == "property" and record.get("property_code") == "dos_fermi")


def _identity(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def scientific_value(record: dict) -> str:
    def clean(item):
        if isinstance(item, dict):
            return {key: clean(value) for key, value in item.items() if value is not None}
        if isinstance(item, list):
            return [clean(value) for value in item]
        if isinstance(item, float) and item.is_integer():
            return int(item)
        return item
    value = {key: record.get(key) for key in SCIENCE_FIELDS}
    for key in ("name_raw", "value_raw", "unit_raw", "canonical_unit"):
        if isinstance(value[key], str):
            value[key] = value[key].strip()
    value["payload"] = {key: item for key, item in (record.get("payload") or {}).items()
                        if key not in {ARCHIVE_KEY, "source_associations", "table_row_ref"}}
    return _identity(clean(value))


def source_records(record: dict) -> list[dict]:
    archive = (record.get("payload") or {}).get(ARCHIVE_KEY)
    if archive is None:
        return [record]
    if (not isinstance(archive, dict) or archive.get("version") != 1
            or isinstance(archive.get("version"), bool) or not isinstance(archive.get("records"), list)
            or not archive["records"]):
        raise ValueError("DOS 来源归档格式或版本无效")
    for source in archive["records"]:
        if (not isinstance(source, dict) or not is_fermi_dos(source)
                or not str(source.get("value_raw") or "").strip()
                or not isinstance(source.get("payload"), dict)
                or ARCHIVE_KEY in (source.get("payload") or {})):
            raise ValueError("DOS 来源必须是非空、无嵌套归档的原始 DOS 记录")
    return archive["records"]


def has_conflict(record: dict) -> bool:
    return is_fermi_dos(record) and len({scientific_value(source) for source in source_records(record)}) > 1


def pending_current_value(record: dict) -> bool:
    return record.get("value_kind") in {"number", "range", "text", "boolean"} and has_conflict(record) and not str(record.get("value_raw") or "").strip() and all(
        record.get(field) in (None, "") for field in VALUE_FIELDS)


def normalize_records(records: list[dict]) -> list[dict]:
    dos = [record for record in records if is_fermi_dos(record)]
    if len(dos) < 2:
        return deepcopy(records)
    # 已有归档标识一条明确的当前记录；它的人工编辑不能变成新的论文来源。
    current = next((record for record in dos if ARCHIVE_KEY in (record.get("payload") or {})), None)
    canonical = deepcopy(current or dos[0])
    sources = []
    seen = set()
    evidences = []
    for record in dos:
        for source in source_records(record):
            copied = deepcopy(source)
            digest = _identity(copied)
            if digest not in seen:
                seen.add(digest)
                sources.append(copied)
            for evidence in [*(source.get("evidences") or []), *([source["evidence"]] if source.get("evidence") else [])]:
                if evidence not in evidences:
                    evidences.append(deepcopy(evidence))
    canonical["payload"] = {**canonical.get("payload", {}), ARCHIVE_KEY: {"version": 1, "records": sources}}
    canonical["evidences"] = evidences
    if current is None and len({scientific_value(source) for source in sources}) > 1:
        canonical["value_raw"] = ""
        for field in VALUE_FIELDS:
            canonical[field] = "" if field == "value_text" and canonical.get("value_kind") == "text" else None
    result = []
    inserted = False
    for record in records:
        if not is_fermi_dos(record):
            result.append(deepcopy(record))
        elif not inserted:
            result.append(canonical)
            inserted = True
    return result

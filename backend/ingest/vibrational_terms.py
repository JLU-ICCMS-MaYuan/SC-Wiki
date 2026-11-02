"""仅归一已经确认的振动层次同义词，不从方法或温度推断物理近似。"""
import re
import unicodedata


def canonical_vibrational_wording(value):
    if not isinstance(value, str):
        return value
    text = unicodedata.normalize("NFKC", value).casefold().replace("\u00ad", "")
    text = re.sub(r"[-‐‑–—_\s]+", " ", text).strip()
    return "harmonic" if text == "harmonic approximation" else value


def normalize_extracted_vibrational_treatment(record):
    """只更新新候选的现有值键；归档原响应和evidences逐字引句由调用链保留。"""
    payload = record.get("payload")
    conditions = payload.get("calculation_conditions") if isinstance(payload, dict) else None
    if isinstance(conditions, dict) and "vibrational_treatment" in conditions:
        conditions["vibrational_treatment"] = canonical_vibrational_wording(conditions["vibrational_treatment"])

"""按 DOI 和标题身份核实出版年；下载、收录、创建日期不是出版年。"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import html
import re
import time
from pathlib import Path
from urllib.parse import quote

import httpx

_CACHE: dict[str, tuple[float, dict]] = {}


def _doi(value):
    return re.sub(r"^https?://(?:dx\.)?doi\.org/", "", str(value or "").strip(), flags=re.I).lower()


def _title(value):
    return re.sub(r"[^\w]", "", html.unescape(re.sub(r"<[^>]*>", "", str(value))).casefold())


def publication_evidence(message: dict, doi: str, title: str) -> dict:
    url = "https://api.crossref.org/works/" + quote(_doi(doi), safe="/")
    base = {"provider": "crossref", "url": url, "doi": _doi(doi)}
    if not isinstance(message, dict):
        return {**base, "status": "unavailable"}
    titles = message.get("title") or []
    if (_doi(message.get("DOI")) != _doi(doi) or len(_title(title)) < 12
            or not isinstance(titles, list) or not any(_title(t) == _title(title) for t in titles)):
        return {**base, "status": "identity_mismatch"}
    dates = {}
    for key in ("published", "published-online", "published-print", "issued"):
        node = message.get(key)
        parts = node.get("date-parts") if isinstance(node, dict) else None
        if (isinstance(parts, list) and parts and isinstance(parts[0], list) and parts[0]
                and type(parts[0][0]) is int and 1600 <= parts[0][0] <= datetime.now().year + 1):
            dates[key] = parts[0]
    years = sorted({v[0] for v in dates.values()})
    if len(years) != 1:
        return {**base, "status": "ambiguous" if years else "unavailable", "dates": dates}
    return {**base, "status": "verified", "year": years[0], "dates": dates,
            "title": titles[0], "verified_at": datetime.now(timezone.utc).isoformat()}


def lookup_publication_year(doi: str, title: str) -> dict:
    """仅在解析/明确重建时调用；成功缓存一小时，失败不伪装成已核实。"""
    if not re.fullmatch(r"10\.\d{4,9}/\S+", _doi(doi)):
        return {"status": "unavailable", "reason": "doi_missing"}
    key = _doi(doi) + ":" + _title(title)
    cached = _CACHE.get(key)
    if cached and cached[0] > time.monotonic():
        return deepcopy(cached[1])
    try:
        response = httpx.get("https://api.crossref.org/works/" + quote(_doi(doi), safe="/"), timeout=10,
                             headers={"User-Agent": "SC-Wiki publication metadata verification"})
        response.raise_for_status()
        result = publication_evidence(response.json()["message"], doi, title)
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        return {"status": "unavailable", "reason": "publication_lookup_failed"}
    if result["status"] == "verified":
        if len(_CACHE) >= 128:
            _CACHE.pop(next(iter(_CACHE)))
        _CACHE[key] = (time.monotonic() + 3600, result)
    return deepcopy(result)


def verify_document_year(document, extracted_paper, *, source_pdf=None, lookup=None):
    """只在年份分歧或出版日期疑似取自水印时查询，不在表单输入/保存时调用。"""
    metadata = (document or {}).get("metadata") or {}
    year = metadata.get("year")
    conflict = year is not None and extracted_paper.get("year") not in (None, year)
    download_date = None
    doi = metadata.get("doi")
    doi_source = None
    date_text = ((document or {}).get("metadata_sources") or {}).get("year", {}).get("text", "")
    if source_pdf:
        import hashlib
        import pymupdf
        path = Path(source_pdf)
        try:
            if hashlib.sha256(path.read_bytes()).hexdigest() != document.get("source_sha256"):
                return {"status": "identity_mismatch", "reason": "source_file_changed"}
            with pymupdf.open(path) as pdf:
                front = pdf[0].get_text()
                if not doi and extracted_paper.get("doi"):
                    candidates = {_doi(value.rstrip('.,;)')) for value in re.findall(r'10\.\d{4,9}/[^\s<>]+', front, re.I)}
                    if _doi(extracted_paper["doi"]) in candidates:
                        doi = _doi(extracted_paper["doi"])
                        doi_source = {"kind": "pdf_text_layer", "pdf_page": 1, "doi": doi,
                                      "source_sha256": document.get("source_sha256")}
                for line in front.splitlines():
                    if not re.search(r"downloaded|printed", line, re.I):
                        continue
                    match = re.search(r"([A-Za-z]+)\s+(\d{1,2}),?\s+(\d{4})", line)
                    months = ['jan','feb','mar','apr','may','jun','jul','aug','sep','oct','nov','dec']
                    if match and match[1][:3].lower() in months:
                        date = f"{int(match[3]):04}-{months.index(match[1][:3].lower()) + 1:02}-{int(match[2]):02}"
                        if str(date_text).startswith(date):
                            download_date = {"date": date, "quote": line}
        except (OSError, ValueError, RuntimeError, IndexError):
            return {"status": "unavailable", "reason": "original_unavailable"}
    if not conflict and not download_date:
        return None
    evidence = (lookup or lookup_publication_year)(doi, metadata.get("title"))
    return {**evidence, "source_sha256": document.get("source_sha256"),
            "original_year": year, "download_date_match": download_date, "doi_source": doi_source}

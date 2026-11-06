"""GROBID原始引文、正式引用持久化及当前审核版本投影。

#225的模型仅在上传解析期核对给定候选；提交、批准和公开读取复用有效依据。
"""

from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
import re
from typing import Any
from xml.etree import ElementTree

import httpx
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import Paper, PaperReference, PaperReferenceExtraction, CitationMatchCache
from backend.services.citation_matching import (
    CitationCatalog, normalize_doi, normalize_title, paper_record, paper_signature, reference_signature,
    related_reference_scope,
)


GROBID_DEFAULT_URL = "http://grobid:8070"
GROBID_NAMESPACE = {"tei": "http://www.tei-c.org/ns/1.0"}
GROBID_TIMEOUT_SECONDS = 90.0
EXTRACTION_STATUSES = {"succeeded", "partial", "failed", "unavailable"}


def _text(element: ElementTree.Element | None) -> str:
    if element is None:
        return ""
    return " ".join(part.strip() for part in element.itertext() if part and part.strip())


def _first_text(element: ElementTree.Element, paths: list[str]) -> str | None:
    for path in paths:
        candidate = _text(element.find(path, GROBID_NAMESPACE))
        if candidate:
            return candidate
    return None


def _author_name(author: ElementTree.Element) -> str | None:
    person = author.find(".//tei:persName", GROBID_NAMESPACE)
    source = person if person is not None else author
    forenames = [_text(item) for item in source.findall(".//tei:forename", GROBID_NAMESPACE)]
    surname = _text(source.find(".//tei:surname", GROBID_NAMESPACE))
    parts = [*filter(None, forenames), surname]
    value = " ".join(parts).strip()
    return value or None


def _extract_year(bibl: ElementTree.Element) -> int | None:
    for date in bibl.findall(".//tei:date", GROBID_NAMESPACE):
        candidate = (date.get("when") or _text(date)).strip()
        match = re.search(r"(?:18|19|20)\d{2}", candidate)
        if match:
            return int(match.group(0))
    return None


def parse_grobid_tei(tei: str | bytes) -> list[dict[str, Any]]:
    """Parse bibliography entries emitted by GROBID's processFulltextDocument."""
    root = ElementTree.fromstring(tei)
    # header 的 biblStruct 是当前论文，不能在 bibliography 缺失时当参考文献。
    entries = root.findall(".//tei:text/tei:back//tei:listBibl/tei:biblStruct", GROBID_NAMESPACE)

    references: list[dict[str, Any]] = []
    for reference_index, bibl in enumerate(entries):
        doi = _first_text(bibl, [
            ".//tei:idno[@type='DOI']",
            ".//tei:idno[@type='doi']",
        ])
        title = _first_text(bibl, [
            ".//tei:analytic/tei:title",
            ".//tei:monogr/tei:title",
            ".//tei:title",
        ])
        authors = [
            author_name
            for author in bibl.findall(".//tei:analytic/tei:author", GROBID_NAMESPACE)
            if (author_name := _author_name(author))
        ]
        if not authors:
            authors = [
                author_name
                for author in bibl.findall(".//tei:monogr/tei:author", GROBID_NAMESPACE)
                if (author_name := _author_name(author))
            ]
        raw_citation = _first_text(bibl, [".//tei:note[@type='raw_reference']"]) or _text(bibl)
        references.append({
            "reference_index": reference_index,
            "raw_citation": raw_citation or "[GROBID 未返回原始引文]",
            "doi": normalize_doi(doi),
            "title": title,
            "normalized_title": normalize_title(title),
            "authors": authors or None,
            "year": _extract_year(bibl),
        })
    return references


def extract_references_from_pdf(
    pdf_path: Path,
    *,
    grobid_url: str | None = None,
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    """Call local GROBID and always return a serializable extraction status.

    A parser outage or malformed TEI is deliberately data, not an upload failure.
    """
    target = f"{(grobid_url or os.getenv('GROBID_URL') or GROBID_DEFAULT_URL).rstrip('/')}/api/processFulltextDocument"
    try:
        with pdf_path.open("rb") as source:
            request_client = client or httpx.Client(
                timeout=httpx.Timeout(GROBID_TIMEOUT_SECONDS, connect=10.0),
            )
            try:
                response = request_client.post(
                    target,
                    params={"consolidateCitations": "0"},
                    files={"input": (pdf_path.name, source, "application/pdf")},
                )
            finally:
                if client is None:
                    request_client.close()
    except (OSError, httpx.RequestError) as exc:
        return {
            "status": "unavailable",
            "parser_name": "grobid",
            "parser_version": None,
            "error_message": str(exc),
            "references": [],
        }

    if response.status_code >= 500:
        return {
            "status": "unavailable",
            "parser_name": "grobid",
            "parser_version": None,
            "error_message": f"GROBID HTTP {response.status_code}",
            "references": [],
        }
    if response.status_code >= 400:
        return {
            "status": "failed",
            "parser_name": "grobid",
            "parser_version": None,
            "error_message": f"GROBID HTTP {response.status_code}",
            "references": [],
        }

    try:
        references = parse_grobid_tei(response.content)
    except ElementTree.ParseError as exc:
        return {
            "status": "failed",
            "parser_name": "grobid",
            "parser_version": None,
            "error_message": f"GROBID TEI 无法解析：{exc}",
            "references": [],
        }
    incomplete = any(not item["doi"] and not item["normalized_title"] for item in references)
    return {
        "status": "partial" if incomplete else "succeeded",
        "parser_name": "grobid",
        "parser_version": response.headers.get("X-GROBID-Version"),
        "error_message": None,
        "references": references,
    }


def _normalized_extraction(extraction: object) -> dict[str, Any]:
    raw = extraction if isinstance(extraction, dict) else {}
    status = raw.get("status")
    if status not in EXTRACTION_STATUSES:
        status = "failed"
    references = raw.get("references")
    return {
        "status": status,
        "parser_name": str(raw.get("parser_name") or "grobid")[:32],
        "parser_version": (str(raw["parser_version"])[:64] if raw.get("parser_version") else None),
        "error_message": (str(raw["error_message"]) if raw.get("error_message") else None),
        "references": references if isinstance(references, list) else [],
    }


async def _catalog(session):
    rows = await session.execute(select(Paper.id, Paper.title, Paper.doi, Paper.year,
                                        Paper.authors, Paper.content_revision).where(
        Paper.review_status == 'approved', Paper.approved_revision == Paper.content_revision))
    return CitationCatalog([dict(row._mapping) for row in rows])


def _reference_value(reference):
    return {key: getattr(reference, key) for key in
            ('reference_index', 'raw_citation', 'title', 'doi', 'year', 'authors')}


def _apply_decision(reference, decision, catalog):
    target = catalog.papers.get(decision.get('paper_id'))
    if not target or decision.get('reference_signature') != reference_signature(_reference_value(reference)):
        return False
    if decision.get('candidate_signature') != paper_signature(target):
        return False
    if decision.get('method') not in ('doi', 'title_year', 'llm2'):
        return False
    if decision['method'] != 'llm2':
        computed = catalog.decide(_reference_value(reference), exclude_id=reference.paper_id)
        if computed['paper_id'] != target['paper_id'] or computed['method'] != decision['method']:
            return False
    reference.cited_paper_id = target['paper_id']
    reference.match_status = 'matched'
    reference.match_method = decision['method']
    reference.match_evidence = decision
    reference.match_checked_at = datetime.now(timezone.utc)
    return True


async def _verified_decision(session, decision):
    if not isinstance(decision, dict):
        return None
    if decision.get('method') != 'llm2':
        return decision
    # 草稿的只读元数据不能伪造服务端模型依据。
    key = decision.get('cache_key')
    cached = await session.get(CitationMatchCache, key) if key else None
    payload = cached.payload if cached else {}
    saved = payload.get('decision') or {}
    if payload.get('state') != 'completed' or saved.get('method') != 'llm2':
        return None
    if saved.get('paper_id') not in (-1, decision.get('paper_id')):
        return None
    if any(saved.get(k) != decision.get(k) for k in
           ('reference_signature', 'candidate_signature', 'model_tag', 'reason')):
        return None
    return {**saved, 'paper_id': decision['paper_id'], 'paper': decision.get('paper')}


async def _match_reference(session: AsyncSession, reference: PaperReference, catalog=None) -> None:
    catalog = catalog or await _catalog(session)
    decision = catalog.decide(_reference_value(reference), exclude_id=reference.paper_id)
    # 人工决定不被自动重试覆盖；目标仍须满足当前公开审核边界。
    if reference.match_method == 'manual' and reference.cited_paper_id in catalog.papers:
        return
    if decision['paper_id'] is not None and _apply_decision(reference, decision, catalog):
        return
    if reference.match_method == 'llm2':
        saved = await _verified_decision(session, reference.match_evidence)
        if saved and _apply_decision(reference, saved, catalog):
            return
    reference.cited_paper_id = None
    reference.match_status = 'ambiguous' if len(decision['candidates']) > 1 else 'unmatched'
    reference.match_method = None
    reference.match_evidence = None
    reference.match_checked_at = datetime.now(timezone.utc)


async def match_references_for_paper(session: AsyncSession, paper: Paper) -> None:
    result = await session.execute(select(PaperReference).where(
        PaperReference.paper_id == paper.id, PaperReference.paper_revision == paper.content_revision))
    catalog = await _catalog(session)
    for reference in result.scalars():
        await _match_reference(session, reference, catalog)


async def persist_reference_extraction(session: AsyncSession, paper: Paper, extraction: object,
                                       matching_snapshot=None) -> None:
    data = _normalized_extraction(extraction)
    old = (await session.scalars(select(PaperReference).where(
        PaperReference.paper_id == paper.id, PaperReference.paper_revision == paper.content_revision))).all()
    previous = {reference_signature(_reference_value(r)): r.match_evidence for r in old if r.match_evidence}
    await session.execute(delete(PaperReference).where(
        PaperReference.paper_id == paper.id, PaperReference.paper_revision == paper.content_revision))
    existing = await session.get(PaperReferenceExtraction, (paper.id, paper.content_revision))
    if existing is None:
        existing = PaperReferenceExtraction(paper_id=paper.id, paper_revision=paper.content_revision)
        session.add(existing)
    existing.status = data['status']
    existing.parser_name = data['parser_name']
    existing.parser_version = data['parser_version']
    existing.error_message = data['error_message']
    existing.processed_at = datetime.now(timezone.utc)
    if isinstance(matching_snapshot, dict):
        existing.matching_snapshot = matching_snapshot
    supplied = {r.get('reference_index', index): r.get('decision') for index, r in
                enumerate((matching_snapshot or {}).get('references', []))}
    catalog = await _catalog(session)
    for index, raw in enumerate(data['references']):
        if not isinstance(raw, dict) or not str(raw.get('raw_citation') or '').strip():
            continue
        reference = PaperReference(paper_id=paper.id, paper_revision=paper.content_revision,
            reference_index=int(raw.get('reference_index', index)), raw_citation=str(raw['raw_citation']).strip(),
            doi=normalize_doi(raw.get('doi')), title=str(raw['title']).strip() if raw.get('title') else None,
            normalized_title=normalize_title(raw.get('title') or raw.get('normalized_title')),
            authors=raw.get('authors') if isinstance(raw.get('authors'), list) else None,
            year=raw.get('year') if isinstance(raw.get('year'), int) else None, match_status='unmatched')
        decision = supplied.get(reference.reference_index) or previous.get(reference_signature(_reference_value(reference)))
        verified = await _verified_decision(session, decision)
        if verified:
            _apply_decision(reference, verified, catalog)
        session.add(reference)
    await session.flush()
    await match_references_for_paper(session, paper)


async def reconcile_after_paper_approval(session: AsyncSession, paper_id: int) -> None:
    paper = await session.get(Paper, paper_id)
    if paper is None or paper.review_status != 'approved' or paper.approved_revision != paper.content_revision:
        return
    catalog = await _catalog(session)
    await match_references_for_paper(session, paper)
    extraction = await session.get(PaperReferenceExtraction, (paper.id, paper.content_revision))
    snapshot = extraction.matching_snapshot if extraction else None
    if isinstance(snapshot, dict) and paper_signature(snapshot.get('paper') or {}) == paper_signature(catalog.papers[paper.id]):
        for incoming in snapshot.get('downstream', []):
            source = catalog.papers.get((incoming.get('paper') or {}).get('paper_id'))
            if not source or paper_signature(source) != paper_signature(incoming.get('paper') or {}):
                continue
            reference = await session.scalar(select(PaperReference).where(
                PaperReference.paper_id == (incoming.get('paper') or {}).get('paper_id'),
                PaperReference.paper_revision == source['revision'],
                PaperReference.reference_index == incoming.get('reference_index')))
            if not source or reference is None or reference.paper_revision != source['revision']:
                continue
            if reference_signature(_reference_value(reference)) != incoming.get('reference_signature'):
                continue
            decision = {**incoming.get('decision', {}), 'paper_id': paper.id,
                        'paper': catalog.papers[paper.id]}
            verified = await _verified_decision(session, decision)
            if verified:
                _apply_decision(reference, verified, catalog)
    # 目标升版或身份修订时，先核验原来指向它的关系，不能保留陈旧模型依据。
    affected = await session.scalars(select(PaperReference).where(PaperReference.cited_paper_id == paper.id))
    for reference in affected:
        await _match_reference(session, reference, catalog)
    result = await session.execute(select(PaperReference).join(Paper, Paper.id == PaperReference.paper_id).where(
        PaperReference.match_status.in_(('unmatched', 'ambiguous')),
        related_reference_scope(catalog.papers[paper.id]),
        PaperReference.paper_revision == Paper.content_revision,
        Paper.review_status == 'approved', Paper.approved_revision == Paper.content_revision))
    for reference in result.scalars():
        if catalog.decide(_reference_value(reference), exclude_id=reference.paper_id)['paper_id'] == paper.id:
            await _match_reference(session, reference, catalog)

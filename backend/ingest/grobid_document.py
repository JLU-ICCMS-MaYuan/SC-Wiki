"""GROBID 题录、引用与正文锚点；不读写数据库，不由 LLM 生成引用。"""
from __future__ import annotations

import hashlib
import json
import os
import re
from copy import deepcopy
from pathlib import Path
import time
from xml.etree import ElementTree as ET

import httpx

NS = {"t": "http://www.tei-c.org/ns/1.0"}


def text(node):
    return " ".join(" ".join(node.itertext()).split()) if node is not None else None


def parse_document(xml):
    from backend.services.citation_graph import parse_grobid_tei, normalize_doi
    root = ET.fromstring(xml)
    header = root.find("t:teiHeader", NS)
    metadata, origins = {}, {}
    if header is not None:
        paths = {"title": ".//t:titleStmt/t:title", "doi": ".//t:idno[@type='DOI']",
                 "journal": ".//t:monogr/t:title[@level='j']", "volume": ".//t:biblScope[@unit='volume']",
                 "issue_number": ".//t:biblScope[@unit='issue']", "pages": ".//t:biblScope[@unit='page']",
                 "abstract": ".//t:abstract"}
        for field, xpath in paths.items():
            node = header.find(xpath, NS)
            value = text(node)
            if value:
                metadata[field] = normalize_doi(value) if field == "doi" else value
                origins[field] = {"xpath": "teiHeader/"+xpath, "text": value, "coordinates": node.get("coords")}
        authors = header.findall(".//t:analytic/t:author/t:persName", NS)
        if authors:
            names = []
            for person in authors:
                names.append(" ".join(filter(None, [*(text(x) for x in person.findall("t:forename", NS)), text(person.find("t:surname", NS))])))
            metadata["authors"] = names
            origins["authors"] = {"xpath": "teiHeader//analytic/author/persName", "text": " | ".join(names)}
        date = header.find(".//t:date[@type='published']", NS)
        if date is None:
            date = header.find(".//t:imprint/t:date", NS)
        if date is not None:
            value = date.get("when") or text(date) or ""
            if len(value) >= 4 and value[:4].isdigit():
                metadata["year"] = int(value[:4])
                origins["year"] = {"xpath": "teiHeader//date", "text": value}
    citations = [{"text": text(node), "targets": (node.get("target") or "").split(),
                  "coordinates": node.get("coords"), "xml_id": node.get("{http://www.w3.org/XML/1998/namespace}id")}
                 for node in root.findall(".//t:text/t:body//t:ref[@type='bibr']", NS)]
    return {"metadata": metadata, "metadata_sources": origins, "references": parse_grobid_tei(xml), "citations": citations}


def extract_document(source, directory, *, timeout=90):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    result = {"status": "unavailable", "parser_name": "grobid", "parser_version": None,
              "references": [], "metadata": {}, "metadata_sources": {}, "citations": [],
              "source_sha256": source.resolved_sha256(), "file_id": source.file_id}
    endpoint = (os.environ.get("GROBID_URL") or "http://127.0.0.1:8070").rstrip("/")
    try:
        with httpx.Client(timeout=httpx.Timeout(timeout, connect=10)) as client:
            version = client.get(endpoint+"/api/version")
            if version.is_success:
                result["parser_version"] = version.text.strip()[:64]
            with source.path.open("rb") as pdf:
                response = client.post(endpoint+"/api/processFulltextDocument", files={"input": (source.path.name, pdf, "application/pdf")},
                    data={"consolidateHeader": "0", "consolidateCitations": "0", "includeRawCitations": "1",
                          "teiCoordinates": ["title", "persName", "biblStruct", "ref"]})
            response.raise_for_status()
        xml_path = directory / "fulltext.tei.xml"
        xml_path.write_bytes(response.content)
        result.update(parse_document(response.content), status="succeeded", tei_sha256=hashlib.sha256(response.content).hexdigest())
    except (OSError, httpx.HTTPError, ET.ParseError) as exc:
        result.update(error_type=type(exc).__name__, error_message="GROBID 题录/引用解析未完成，需要人工核对")
    result["elapsed_seconds"] = time.monotonic()-started
    (directory / "document.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def _bounded_abstract(document, ir):
    """仅在独立版面块确认关键词分隔时截去误串入摘要的正文，保留原解析。"""
    if ir is None or ir.source_sha256 != document.get("source_sha256"):
        return document
    abstract = document.get("metadata", {}).get("abstract")
    if not isinstance(abstract, str):
        return document
    blocks = sorted((b for b in ir.blocks if b.pdf_page == 1 and b.text
                     and b.metadata.get("selected_for_reading") is not False), key=lambda b: b.reading_order)
    def words(value):
        return re.findall(r"[a-z]+", value.lower())
    for index, block in enumerate(blocks):
        marker = " ".join(block.text.split())
        if index == 0 or "|" not in marker or not 2 <= len(marker.split()) <= 20 or abstract.count(marker) != 1:
            continue
        prefix, suffix = abstract.split(marker)
        prior = words(blocks[index - 1].text)
        selected = words(prefix)
        if (len(prior) < 70 or len(selected) < 70 or len(suffix.split()) < 30
                or selected[:12] != prior[:12] or selected[-8:] != prior[-8:]):
            continue
        corrected = deepcopy(document)
        corrected["metadata"]["abstract"] = prefix.strip()
        corrected.setdefault("metadata_sources", {}).setdefault("abstract", {"text": abstract}).update(
            selected_text=prefix.strip(), selection_rule="layout-keyword-boundary-v1",
            boundary_block_id=block.block_id, abstract_block_id=blocks[index - 1].block_id)
        return corrected
    return document


def apply_bibliography(draft, document, *, main_ir=None, publication_verification=None):
    """只用已确定的正文题录组装字段；保留模型分歧，不改科学分类。"""
    if not document or document.get("status") != "succeeded":
        return
    original_metadata = deepcopy(document.get("metadata", {}))
    document = deepcopy(_bounded_abstract(document, main_ir))
    if publication_verification:
        from .publication_year import _doi, _title
        evidence = deepcopy(publication_verification)
        metadata = document["metadata"]
        same_file = evidence.get("source_sha256") == document.get("source_sha256")
        doi_source = evidence.get("doi_source") or {}
        matched_doi = _doi(metadata.get("doi")) or (
            _doi(draft.get("paper", {}).get("doi"))
            if doi_source.get("source_sha256") == document.get("source_sha256") and doi_source.get("doi") == evidence.get("doi") else "")
        valid = (same_file and evidence.get("status") == "verified"
                 and matched_doi == evidence.get("doi")
                 and _title(metadata.get("title")) == _title(evidence.get("title")))
        if evidence.get("status") == "verified" and not valid:
            evidence["status"] = "identity_mismatch"
        if valid:
            metadata["year"] = evidence["year"]
        elif same_file and evidence.get("download_date_match"):
            metadata["year"] = None
        document.setdefault("metadata_sources", {}).setdefault("year", {}).update(publication_verification=evidence)
    paper = draft.setdefault("paper", {})
    conflicts = []
    for field, value in document.get("metadata", {}).items():
        original = original_metadata.get(field, value)
        if paper.get(field) not in (None, "", [], original) or original != value:
            conflicts.append({"field": field, "grobid_value": original,
                              "extracted_value": paper.get(field), "selected_value": value})
        paper[field] = value
    draft["bibliography_sources"] = {"file_id": document["file_id"], "source_sha256": document["source_sha256"],
                                     "parser_version": document["parser_version"], "fields": document["metadata_sources"]}
    draft["bibliography_conflicts"] = conflicts

"""公开期刊入口及内容语义；只保留书目元数据，不抓取论文全文。"""
from datetime import datetime, timezone
import calendar
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import feedparser

from .domain import (CollectionError, Record, content_kind, iso, normalize_doi,
                     plain, safe_url, scholarly_relevance_evidence)

PUBLISHER_FEEDS = {
    "aps": tuple((name, f"https://feeds.aps.org/rss/recent/{code}.xml") for code, name in (
        ("prl", "Physical Review Letters"), ("prb", "Physical Review B"), ("prx", "Physical Review X"))),
    "nature": tuple((name, f"https://www.nature.com/{code}.rss") for code, name in (
        ("nature", "Nature"), ("nphys", "Nature Physics"), ("nmat", "Nature Materials"),
        ("ncomms", "Nature Communications"))),
    "science": tuple(("Science", f"https://www.science.org/action/showFeed?type={kind}&feed=rss&jc=science")
                     for kind in ("etoc", "axatoc")),
    "materials_today": (("Materials Today", "https://rss.sciencedirect.com/publication/science/13697021"),),
}
PUBLISHER_FILTERS = {
    "aps": "prefix:10.1103", "acs": "prefix:10.1021", "nature": "prefix:10.1038", "science": "prefix:10.1126",
    "nsr": "issn:2095-5138", "cpl": "issn:0256-307X", "cpb": "issn:1674-1056", "materials_today": "issn:1369-7021",
}
JOURNAL_DOI_PREFIXES = {
    "nsr": ("10.1093/nsr/",), "cpl": ("10.1088/0256-307x/",),
    "cpb": ("10.1088/1674-1056/",), "materials_today": ("10.1016/j.mattod.", "10.1016/s1369-7021"),
}
SEARCH_TERMS = ("superconductivity", "superconducting", "superconductor", "Josephson")


def matches_publisher(item, source):
    selector, value = PUBLISHER_FILTERS[source].split(":", 1)
    doi = normalize_doi(item.get("DOI", ""))
    if selector == "prefix":
        return doi.startswith(value + "/")
    return value.lower() in {str(v).lower() for v in item.get("ISSN", [])} or any(
        doi.startswith(prefix) for prefix in JOURNAL_DOI_PREFIXES[source])


def original_url(url):
    """去除明确的订阅追踪参数；不删除有业务含义的其他查询参数。"""
    parts = urlsplit(safe_url(url))
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
             if not k.startswith("utm_") and k not in {"dgcid", "af"}]
    scheme = "https" if parts.hostname in {"link.aps.org", "doi.org", "www.nature.com", "www.science.org"} else parts.scheme
    return urlunsplit((scheme, parts.netloc, parts.path, urlencode(query), ""))


def publication_date(entry):
    for key in ("published", "updated"):
        if entry.get(key + "_parsed"):
            value = str(entry.get(key, ""))
            precision = "year" if re.fullmatch(r"\d{4}", value) else "month" if re.fullmatch(r"\d{4}-\d{2}", value) else "day"
            return iso(datetime.fromtimestamp(calendar.timegm(entry[key + "_parsed"]), timezone.utc)), precision
    match = re.search(r"Publication date:\s*(?:Available online\s*)?([^<]+)", entry.get("summary", ""), re.I)
    if match:
        for pattern, precision in (("%d %B %Y", "day"), ("%B %Y", "month"), ("%Y", "year")):
            try:
                return iso(datetime.strptime(match[1].strip(), pattern).replace(tzinfo=timezone.utc)), precision
            except ValueError:
                pass
    return "", "unknown"


def publisher_records(content, source, journal, since):
    parsed = feedparser.parse(content)
    if parsed.get("bozo") or not parsed.get("version"):
        raise CollectionError("invalid_feed")
    records = []
    for entry in parsed.entries:
        title = plain(entry.get("title", ""), 4000)
        excerpt = plain(entry.get("summary", ""))
        evidence = scholarly_relevance_evidence(title, excerpt)
        if not title or not evidence:
            continue
        url = original_url(entry.get("link", ""))
        # 出版商订阅源只能生成该出版商的原文落地页，不信任外部条目的任意跳转。
        host = (urlsplit(url).hostname or "").lower()
        allowed = {"aps": ("aps.org",), "nature": ("nature.com",), "science": ("science.org",),
                   "materials_today": ("sciencedirect.com",)}[source]
        if not any(host == domain or host.endswith("." + domain) for domain in allowed):
            raise CollectionError("invalid_record")
        doi = normalize_doi(entry.get("prism_doi", "") or entry.get("dc_identifier", ""))
        if not doi:
            match = re.search(r"10\.\d{4,9}/[^\s?<>\"'&]+", url)
            doi = normalize_doi(match.group(0)) if match else ""
        if doi and not matches_publisher({"DOI": doi}, source):
            raise CollectionError("invalid_record")
        published, precision = publication_date(entry)
        if precision == "day" and published and published < iso(since):
            continue
        genre = str(entry.get("dc_type", "")).casefold().strip()
        report = genre in {"news", "news article", "news & views", "research highlight", "editorial", "book review"}
        kind = content_kind("news" if report else "journal_article", doi=doi, source=source, url=url)
        records.append(Record(source=source, external_id=doi or url, kind=kind, title=title, url=url, doi=doi,
                              authors=[plain(a.get("name", ""), 400) for a in entry.get("authors", []) if a.get("name")],
                              journal=journal, published_at=published, date_precision=precision,
                              source_updated_at=published, content_type="research_report" if kind == "news" else "journal_article",
                              display_kind=kind, discovery_source=source, original_source=source, relevance_evidence=evidence))
    return records, len(parsed.entries)

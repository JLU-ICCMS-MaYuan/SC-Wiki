"""固定官方端点适配；只接收元数据，不请求条目中的外链。"""
import calendar
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
import json
import os
import re
import time

import feedparser
import httpx

from .domain import (CollectionError, PUBLISHER_SOURCES, Record, canonical_url, content_kind, iso, normalize_doi, parse_time, plain,
                     publisher_for_doi, relevance_evidence, relevant, safe_url, scholarly_relevance_evidence)
from .publishers import PUBLISHER_FEEDS, PUBLISHER_FILTERS, SEARCH_TERMS, matches_publisher, original_url, publisher_records

ENDPOINTS = {
    "arxiv": "https://export.arxiv.org/api/query",
    "crossref": "https://api.crossref.org/works",
    "openalex": "https://api.openalex.org/works",
    "physorg": "https://phys.org/rss-feed/physics-news/superconductivity/",
    "google_news": "https://news.google.com/rss/search",
}
ENDPOINTS.update({source: ENDPOINTS["crossref"] for source in PUBLISHER_SOURCES})
OPENALEX_MIN_LOOKBACK_DAYS = 30


class Transport:
    def __init__(self, client=None, direct_client=None, sleep=time.sleep, contact=""):
        options = dict(
            timeout=httpx.Timeout(30, connect=10),
            limits=httpx.Limits(max_connections=1, max_keepalive_connections=1),
            follow_redirects=False,
            headers={"User-Agent": "SC-Wiki-News/1.0 (+https://github.com/JLU-ICCMS-MaYuan/SC-Wiki)" +
                     (f" mailto:{contact}" if contact else "")},
        )
        # 科学元数据端点在当前部署环境可直连；仅 Google News 使用系统代理。
        # 分开连接池可避免本地代理抖动拖垮论文采集，同时保留被网络限制的新闻源。
        self.client = client or httpx.Client(**options)
        self.direct_client = direct_client or (self.client if client else httpx.Client(**options, trust_env=False))
        self.sleep = sleep
        self.guard = lambda: None

    def close(self):
        if self.direct_client is not self.client:
            self.direct_client.close()
        self.client.close()

    def get(self, source, url, params=None, headers=None):
        allowed = {ENDPOINTS.get(source), *(url for _, url in PUBLISHER_FEEDS.get(source, ())) }
        if url not in allowed:
            raise CollectionError("invalid_record")
        for attempt in range(3):
            self.guard()
            # 每次请求都等待，跨分页、重试及手动运行保持来源限速。
            self.sleep(3.1 if source == "arxiv" else 1.0)
            try:
                request_client = self.client if source == "google_news" else self.direct_client
                with request_client.stream("GET", url, params=params, headers=headers) as response:
                    if response.status_code == 429 or response.status_code >= 500:
                        code = "rate_limited" if response.status_code == 429 else "http_error"
                        if attempt == 2:
                            raise CollectionError(code)
                        retry = response.headers.get("Retry-After", "")
                        try:
                            delay = float(retry) if retry else 2 ** (attempt + 1)
                        except ValueError:
                            try:
                                delay = (parsedate_to_datetime(retry) - datetime.now(timezone.utc)).total_seconds()
                            except (ValueError, TypeError):
                                delay = 2 ** (attempt + 1)
                        if delay > 60:
                            raise CollectionError(code)
                        self.sleep(max(0, delay))
                        continue
                    if response.status_code == 401:
                        raise CollectionError("authentication_required")
                    if response.status_code == 403:
                        raise CollectionError("access_denied")
                    if response.status_code == 400:
                        raise CollectionError("bad_request")
                    if response.status_code != 200:
                        raise CollectionError("http_error")
                    content = bytearray()
                    for chunk in response.iter_bytes():
                        self.guard()
                        content.extend(chunk)
                        if len(content) > 5 * 1024 * 1024:
                            raise CollectionError("invalid_feed")
                    return bytes(content)
            except httpx.HTTPError as exc:
                if attempt == 2:
                    raise CollectionError("http_error") from exc
                self.sleep(2 ** (attempt + 1))
        raise CollectionError("http_error")


def feed(content):
    parsed = feedparser.parse(content)
    if parsed.get("bozo") or not parsed.get("version"):
        raise CollectionError("invalid_feed")
    return parsed


def rss_time(entry, name):
    value = entry.get(name + "_parsed")
    if not value:
        raise CollectionError("invalid_record")
    return iso(datetime.fromtimestamp(calendar.timegm(value), timezone.utc))


def crossref_date(item):
    for field in ("published-online", "published", "published-print"):
        parts = item.get(field, {}).get("date-parts")
        if parts and parts[0]:
            values = parts[0]
            try:
                date = datetime(values[0], values[1] if len(values) > 1 else 1,
                                values[2] if len(values) > 2 else 1, tzinfo=timezone.utc)
            except (ValueError, TypeError):
                raise CollectionError("invalid_record")
            return iso(date), ("year", "month", "day")[min(len(values), 3) - 1]
    return "", "unknown"


class Sources:
    def __init__(self, transport=None, max_pages=100, contact="", openalex_key=None):
        self.transport = transport or Transport(contact=contact)
        self.max_pages = max_pages
        self.contact = contact
        self.openalex_key = os.getenv("NEWS_OPENALEX_API_KEY", "") if openalex_key is None else openalex_key
        self.partial_error = ""
        self.endpoint_errors = []

    def fetch(self, source, since, until):
        self.fetched = 0
        self.partial_error = ""
        self.endpoint_errors = []
        if source not in ENDPOINTS:
            raise CollectionError("invalid_record")
        result = self.publisher(source, since, until) if source in PUBLISHER_SOURCES else getattr(self, source)(since, until)
        for row in result:
            row.validate()
        return result

    def arxiv(self, since, until):
        result = []
        for page in range(self.max_pages):
            parsed = feed(self.transport.get("arxiv", ENDPOINTS["arxiv"], {
                "search_query": "cat:cond-mat.supr-con", "sortBy": "lastUpdatedDate",
                "sortOrder": "descending", "start": page * 100, "max_results": 100,
            }))
            try:
                total = int(parsed.feed["opensearch_totalresults"])
            except (KeyError, ValueError, TypeError):
                raise CollectionError("invalid_feed")
            if not parsed.entries and page * 100 < total:
                raise CollectionError("invalid_feed")
            self.fetched += len(parsed.entries)
            for entry in parsed.entries:
                match = re.fullmatch(r"https?://arxiv.org/abs/((?:\d{4}\.\d{4,5}|[a-z.-]+/\d{7}))(?:v(\d+))?", entry.get("id", ""))
                if not match:
                    raise CollectionError("invalid_record")
                updated = rss_time(entry, "updated")
                if parse_time(updated) < since:
                    return result
                if parse_time(updated) > until:
                    continue
                if not any(tag.get("term") == "cond-mat.supr-con" for tag in entry.get("tags", [])):
                    continue
                aid, version = match.groups()
                result.append(Record(
                    source="arxiv", external_id=aid, kind="preprint",
                    title=plain(entry.get("title", ""), 4000), url="https://arxiv.org/abs/" + aid,
                    summary=plain(entry.get("summary", "")), summary_source="arxiv",
                    doi=normalize_doi(entry.get("arxiv_doi", "")), arxiv_id=aid, version=int(version or 1),
                    authors=[plain(a.get("name", ""), 120) for a in entry.get("authors", [])][:100],
                    published_at=rss_time(entry, "published"), source_updated_at=updated,
                ))
            if (page + 1) * 100 >= total:
                return result
            if len(parsed.entries) < 100:
                raise CollectionError("invalid_feed")
        raise CollectionError("page_limit")

    def crossref(self, since, until):
        since = min(since, until - timedelta(days=30))
        return self._crossref_search("crossref", since, until)

    def publisher(self, source, since, until):
        result, successes = [], 0
        since = min(since, until - timedelta(days=30))
        for journal, endpoint in PUBLISHER_FEEDS.get(source, ()):
            try:
                records, count = publisher_records(self.transport.get(source, endpoint), source, journal, since)
                self.fetched += count
                result.extend(records)
                successes += 1
            except CollectionError as exc:
                self.endpoint_errors.append(f"{source}:rss:{journal}:{exc}")
        try:
            result.extend(self._crossref_search(source, since, until))
            successes += 1
        except CollectionError as exc:
            self.endpoint_errors.append(f"{source}:crossref:{exc}")
        if not successes:
            raise CollectionError("publisher_unavailable")
        if self.endpoint_errors:
            self.partial_error = "publisher_partial"
        # 各入口的记录交给事务层按 DOI/URL 合并，保留真实发现来源和更完整的元数据。
        return result

    @staticmethod
    def _unique(records):
        unique = {}
        for record in records:
            unique.setdefault(record.doi or canonical_url(record.url), record)
        return list(unique.values())

    def _crossref_search(self, source, since, until):
        result, successes, failures = [], 0, []
        for term in SEARCH_TERMS:
            try:
                result.extend(self._crossref(source, since, until, term))
                successes += 1
            except CollectionError as exc:
                failures.append(str(exc))
        if not successes:
            raise CollectionError(failures[0])
        if failures:
            self.partial_error = "crossref_partial"
        return self._unique(result)

    def _crossref(self, source, since, until, term):
        result, cursor, previous_ids = [], "*", None
        for _ in range(self.max_pages):
            filters = f"type:journal-article,from-pub-date:{since.date()},until-pub-date:{until.date()}"
            if source in PUBLISHER_FILTERS:
                filters += "," + PUBLISHER_FILTERS[source]
            params = {"query": term, "filter": filters,
                "rows": 100, "cursor": cursor, "sort": "indexed", "order": "desc"}
            if self.contact:
                params["mailto"] = self.contact
            try:
                body = json.loads(self.transport.get(source, ENDPOINTS[source], params))["message"]
                items = body["items"]
                if not isinstance(items, list):
                    raise ValueError("items")
            except CollectionError as exc:
                if result:
                    self.partial_error = str(exc)
                    return result
                raise
            except (KeyError, ValueError, TypeError):
                if result:
                    self.partial_error = "invalid_feed"
                    return result
                raise CollectionError("invalid_feed")
            self.fetched += len(items)
            ids = [item.get("DOI") for item in items]
            if ids and ids == previous_ids:
                self.partial_error = "invalid_feed"
                return result
            previous_ids = ids
            for item in items:
                title = plain(" ".join(item.get("title", [])), 4000)
                if not title:
                    self.partial_error = "invalid_record"
                    continue
                evidence = scholarly_relevance_evidence(title, plain(item.get("abstract", "")))
                if item.get("type") != "journal-article" or not evidence:
                    continue
                if source in PUBLISHER_FILTERS and not matches_publisher(item, source):
                    continue
                doi = normalize_doi(item.get("DOI", ""))
                if not doi:
                    self.partial_error = "invalid_record"
                    continue
                try:
                    published, precision = crossref_date(item)
                    updated = item.get("indexed", {}).get("date-time", "")
                    if updated:
                        updated = iso(parse_time(updated))
                except CollectionError:
                    self.partial_error = "invalid_record"
                    continue
                if published and precision == "day" and not since.date().isoformat() <= published[:10] <= until.date().isoformat():
                    continue
                resource = (item.get("resource") or {}).get("primary") or {}
                try:
                    url = original_url(resource.get("URL") or "https://doi.org/" + doi)
                except CollectionError:
                    url = "https://doi.org/" + doi
                kind = content_kind("journal_article", doi=doi, url=url)
                result.append(Record(
                    source=source, external_id=doi, kind=kind,
                    title=title, doi=doi, url=url,
                    authors=[plain(" ".join(filter(None, [a.get("given"), a.get("family"), a.get("name")])), 120)
                             for a in item.get("author", [])][:100],
                    journal=plain(" ".join(item.get("container-title", [])), 1000),
                    published_at=published, date_precision=precision, source_updated_at=updated,
                    content_type="research_report" if kind == "news" else "journal_article", display_kind=kind, discovery_source="crossref",
                    original_source=publisher_for_doi(doi) or (source if source in PUBLISHER_SOURCES else ""), relevance_evidence=evidence,
                ))
            if len(items) < 100:
                return result
            next_cursor = body.get("next-cursor")
            if not next_cursor:
                self.partial_error = "invalid_feed"
                return result
            cursor = next_cursor
        self.partial_error = "page_limit"
        return result

    def openalex(self, since, until):
        result, cursor = [], "*"
        # 免费 OpenAlex API 不提供 updated_date 增量过滤。滚动回看出版日期并依靠本地身份键
        # 去重，避免新近收录但出版已超过通用两天重叠窗口的论文永久漏失。
        since = min(since, until - timedelta(days=OPENALEX_MIN_LOOKBACK_DAYS))
        for _ in range(self.max_pages):
            params = {
                "search": "superconduct",
                "filter": (f"from_publication_date:{since.date()},to_publication_date:{until.date()},"
                           "type:article|review,primary_location.source.type:journal"),
                "per-page": 100,
                "cursor": cursor,
            }
            try:
                # 官方支持 Bearer；避免把Key放在会被HTTP客户端记录的查询URL中。
                headers = {"Authorization": "Bearer " + self.openalex_key} if self.openalex_key else None
                body = json.loads(self.transport.get("openalex", ENDPOINTS["openalex"], params, headers=headers))
                items = body["results"]
                if not isinstance(items, list):
                    raise ValueError("results")
            except CollectionError as exc:
                if result:
                    self.partial_error = str(exc)
                    return result
                raise
            except (KeyError, ValueError, TypeError):
                if result:
                    self.partial_error = "invalid_feed"
                    return result
                raise CollectionError("invalid_feed")
            self.fetched += len(items)
            for item in items:
                location = item.get("primary_location") or {}
                source = location.get("source") or {}
                if (item.get("type") not in {"article", "review"} or source.get("type") != "journal"
                        or location.get("is_published") is False or location.get("is_accepted") is False):
                    continue
                title = plain(item.get("title", ""), 4000)
                abstract = openalex_abstract(item.get("abstract_inverted_index"))
                evidence = scholarly_relevance_evidence(
                    title, abstract, openalex_metadata_text(item), source.get("display_name", "")
                )
                if not title or not evidence:
                    continue
                doi = normalize_doi(item.get("doi", ""))
                # OpenAlex 偶尔把 Zenodo 上传映射到期刊主来源；该 DOI 前缀不能证明同行评审。
                if doi.startswith("10.5281/"):
                    continue
                try:
                    url = safe_url(location.get("landing_page_url") or ("https://doi.org/" + doi if doi else item.get("id", "")))
                except CollectionError:
                    self.partial_error = "invalid_record"
                    continue
                published = item.get("publication_date", "")
                if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", published):
                    self.partial_error = "invalid_record"
                    continue
                updated = item.get("updated_date", "")
                if updated:
                    try:
                        updated = iso(parse_time(_openalex_timestamp(updated)))
                    except CollectionError:
                        self.partial_error = "invalid_record"
                        continue
                authors = [plain((row.get("author") or {}).get("display_name", ""), 120)
                           for row in item.get("authorships", [])][:100]
                journal = plain(((location.get("source") or {}).get("display_name", "")), 1000)
                external_id = str(item.get("id", "")).rsplit("/", 1)[-1]
                if not external_id:
                    self.partial_error = "invalid_record"
                    continue
                kind = content_kind("journal_article", doi=doi, url=url)
                result.append(Record(
                    source="openalex", external_id=external_id, kind=kind, title=title, url=url,
                    summary=abstract, summary_source="openalex" if abstract else "", doi=doi, authors=authors,
                    journal=journal, published_at=published + "T00:00:00Z", source_updated_at=updated,
                    content_type="research_report" if kind == "news" else "journal_article", display_kind=kind, discovery_source="openalex",
                    original_source=publisher_for_doi(doi), relevance_evidence=evidence,
                ))
            next_cursor = (body.get("meta") or {}).get("next_cursor")
            total = (body.get("meta") or {}).get("count")
            if not next_cursor or not items or (isinstance(total, int) and self.fetched >= total):
                return result
            if not self.openalex_key:
                self.partial_error = "openalex_key_required"
                return result
            cursor = next_cursor
        self.partial_error = "page_limit"
        return result

    def physorg(self, since, until):
        parsed = feed(self.transport.get("physorg", ENDPOINTS["physorg"]))
        self.fetched = len(parsed.entries)
        result = []
        for entry in parsed.entries:
            published = rss_time(entry, "published")
            if not since <= parse_time(published) <= until:
                continue
            url = safe_url(entry.get("link", ""))
            # 官方专栏为范围保证；外链仍限制在官方新闻站点。
            if httpx.URL(url).host != "phys.org":
                raise CollectionError("invalid_record")
            title = entry.get("title", "").strip()
            result.append(Record(
                source="physorg", external_id=canonical_url(url), kind="news", title=title,
                url=url, summary=plain(entry.get("summary", "")), summary_source="physorg",
                published_at=published, source_updated_at=published,
                content_type="research_report", display_kind="news", discovery_source="physorg",
                original_source="physorg", relevance_evidence=relevance_evidence(title, entry.get("summary", "")),
            ))
        return result

    def google_news(self, since, until):
        parsed = feed(self.transport.get("google_news", ENDPOINTS["google_news"], {
            "q": "superconduct OR 超导", "hl": "en-US", "gl": "US", "ceid": "US:en",
        }))
        self.fetched = len(parsed.entries)
        result = []
        for entry in parsed.entries:
            title = plain(entry.get("title", ""), 4000)
            summary = plain(entry.get("summary", ""))
            evidence = relevance_evidence(title, summary)
            if not evidence:
                continue
            published = rss_time(entry, "published")
            if not since <= parse_time(published) <= until:
                continue
            url = safe_url(entry.get("link", ""))
            result.append(Record(
                source="google_news", external_id=canonical_url(url), kind="news", title=title, url=url,
                summary=summary, summary_source="google_news", published_at=published, source_updated_at=published,
                content_type="social_industry", display_kind="news", discovery_source="google_news",
                original_source="", relevance_evidence=evidence,
            ))
        return result


def openalex_abstract(index):
    if not isinstance(index, dict):
        return ""
    words = []
    for word, positions in index.items():
        if not isinstance(positions, list):
            return ""
        words.extend((position, word) for position in positions if isinstance(position, int) and position >= 0)
    return " ".join(word for _, word in sorted(words))


def openalex_metadata_text(item):
    """提取达到最低置信度的 OpenAlex 主题元数据，不将整份上游响应入库。"""
    labels = []
    for field, threshold in (("keywords", 0.5), ("topics", 0.2), ("concepts", 0.5)):
        for value in item.get(field) or []:
            if isinstance(value, dict) and _openalex_score(value) >= threshold:
                labels.append(str(value.get("display_name", "")))
    topic = item.get("primary_topic") or {}
    if isinstance(topic, dict) and _openalex_score(topic) >= 0.2:
        labels.append(str(topic.get("display_name", "")))
    return " ".join(labels)


def _openalex_score(value):
    try:
        return float(value.get("score", 0))
    except (TypeError, ValueError):
        return 0


def _openalex_timestamp(value):
    """OpenAlex 的 updated_date 文档语义为 UTC，但有时省略时区后缀。"""
    value = str(value or "").strip()
    if value and not re.search(r"(?:Z|[+-]\d{2}:\d{2})$", value, re.I):
        value += "Z"
    return value

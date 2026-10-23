"""期刊发现、语义、分页权限与部分成功的独立验证。"""
from datetime import datetime, timedelta, timezone
from dataclasses import replace
import json
import logging

import httpx
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from backend.news.domain import CollectionError, Record, content_kind, iso
from backend.news.models import NewsFeedItem, NewsFeedIdentity, NewsFeedSource
from backend.news.publishers import PUBLISHER_FILTERS, SEARCH_TERMS, publisher_records
from backend.news.sources import Sources, Transport, crossref_date
from backend.news.service import collect_source, upsert
from backend.news.scheduler import due

NOW = datetime(2026, 10, 23, tzinfo=timezone.utc)


@pytest.mark.parametrize("doi,url", [("10.1038/d41586-026-00001", ""), ("10.1103/physics.19.1", ""), ("10.1021/cen-v100n001.p01", ""),
                                     ("", "http://www.science.org/content/article/report")])
def test_publisher_news_identifiers(doi, url):
    assert content_kind("journal_article", doi=doi, url=url) == "news"


def transport(handler):
    return Transport(httpx.Client(transport=httpx.MockTransport(handler)), sleep=lambda _: None)


@pytest.mark.parametrize("status,code", [(400,"bad_request"),(401,"authentication_required"),(403,"access_denied")])
def test_diagnostic_http_codes_do_not_include_upstream_body(status, code):
    client=transport(lambda _:httpx.Response(status,text="sensitive upstream response"))
    with pytest.raises(CollectionError,match="^"+code+"$"):
        client.get("openalex","https://api.openalex.org/works")


@pytest.fixture
def engine():
    db = create_engine("sqlite://")
    for model in (NewsFeedItem, NewsFeedIdentity, NewsFeedSource):
        model.__table__.create(db)
    yield db
    db.dispose()


def oa_page(cursor="next"):
    return {"results": [{"id": "https://openalex.org/W1", "type": "review", "title": "Review of superconductivity",
                         "doi": "https://doi.org/10.1103/test", "publication_date": "2026-10-22",
                         "primary_location": {"source": {"type": "journal", "display_name": "Test journal"}}}],
            "meta": {"count": 200, "next_cursor": cursor}}


def test_no_key_retains_first_page_without_claiming_complete(engine, caplog):
    calls = []
    def get(req):
        calls.append(req)
        return httpx.Response(200, json=oa_page())
    src = Sources(transport(get), openalex_key="")
    assert not collect_source(engine, "openalex", src, now=NOW)
    assert len(calls) == 1
    with Session(engine) as db:
        state = db.get(NewsFeedSource, "openalex")
        assert state.status == "partial" and state.error_code == "openalex_key_required"
        assert state.last_success_at == "" and state.accepted == 1
        assert len(list(db.scalars(select(NewsFeedItem)))) == 1
        assert not due(state, NOW, NOW + timedelta(minutes=30))
        assert due(state, NOW, NOW + timedelta(hours=1))


def test_key_allows_full_paging_and_failure_does_not_discard_first_page(engine, caplog):
    caplog.set_level(logging.INFO)
    calls = []
    def get(req):
        assert req.headers["Authorization"] == "Bearer fixture-private-key"
        assert "api_key" not in req.url.params
        calls.append(req)
        return httpx.Response(200, json=oa_page()) if req.url.params["cursor"] == "*" else httpx.Response(401)
    src = Sources(transport(get), openalex_key="fixture-private-key")
    with Session(engine) as db, db.begin():
        db.add(NewsFeedSource(source="openalex", status="success", last_success_at=iso(NOW - timedelta(days=1))))
    assert not collect_source(engine, "openalex", src, now=NOW)
    assert len(calls) == 2 and "fixture-private-key" not in caplog.text
    with Session(engine) as db:
        state = db.get(NewsFeedSource, "openalex")
        assert state.last_success_at == iso(NOW - timedelta(days=1))
        assert state.error_code == "authentication_required"
        assert len(list(db.scalars(select(NewsFeedItem)))) == 1
    src.transport = transport(lambda req: httpx.Response(200, json=oa_page() if req.url.params["cursor"] == "*" else {"results": [], "meta": {}}))
    assert collect_source(engine, "openalex", src, now=NOW + timedelta(hours=1))
    with Session(engine) as db:
        assert db.get(NewsFeedSource, "openalex").status == "success"
        assert len(list(db.scalars(select(NewsFeedItem)))) == 1


def test_no_key_is_complete_when_all_results_fit_one_page():
    page = oa_page();page["meta"]["count"] = 1
    src = Sources(transport(lambda _: httpx.Response(200, json=page)), openalex_key="")
    assert len(src.fetch("openalex", NOW - timedelta(days=1), NOW)) == 1
    assert not src.partial_error


def rss(doi="10.1103/example", domain="journals.aps.org", genre="Research Article"):
    return f'''<rss version="2.0" xmlns:dc="http://purl.org/dc/elements/1.1/">
    <channel><title>Journal</title><item><title>Superconductivity in a material</title>
    <link>https://{domain}/article/{doi}</link><dc:identifier>doi:{doi}</dc:identifier><dc:type>{genre}</dc:type>
    <pubDate>Thu, 22 Oct 2026 10:00:00 GMT</pubDate><description>Superconducting critical temperature.</description>
    </item></channel></rss>'''.encode()


@pytest.mark.parametrize("doi,genre,kind", [("10.1038/test", "Research Article", "journal_article"),
                                           ("10.1038/d41586-026-00001", "", "news"),
                                           ("10.1038/test", "News Article", "news"),
                                           ("10.1038/test", "Review", "journal_article")])
def test_publisher_website_is_not_enough_to_claim_journal(doi, genre, kind):
    records, count = publisher_records(rss(doi, "www.nature.com", genre), "nature", "Nature", NOW - timedelta(days=7))
    assert count == 1 and records[0].kind == records[0].display_kind == kind
    assert records[0].doi == doi and records[0].date_precision == "day"
    assert records[0].summary == ""  # 新期刊订阅源只保存元数据。


def test_rss_failure_does_not_discard_other_endpoint_records(engine):
    def get(req):
        if req.url.host == "feeds.aps.org":
            return httpx.Response(200, content=rss()) if req.url.path.endswith("prb.xml") else httpx.Response(403)
        return httpx.Response(200, json={"message": {"items": []}})
    src = Sources(transport(get))
    assert not collect_source(engine, "aps", src, now=NOW)
    with Session(engine) as db:
        state = db.get(NewsFeedSource, "aps")
        assert state.status == "partial" and state.error_code == "publisher_partial"
        item = db.scalar(select(NewsFeedItem))
        assert item.discovery_source == "aps" and item.kind == "journal_article"


@pytest.mark.parametrize("source,doi,issn", [("nsr", "10.1093/nsr/nwag001", "2095-5138"),
    ("cpl", "10.1088/0256-307x/test", "0256-307X"), ("cpb", "10.1088/1674-1056/test", "1674-1056"),
    ("materials_today", "10.1016/j.mattod.2026.001", "1369-7021")])
def test_crossref_uses_journal_identity_and_all_word_forms(source, doi, issn):
    seen = []
    good = {"DOI": doi, "ISSN": [issn], "type": "journal-article", "title": ["Superconductivity in a material"],
            "published": {"date-parts": [[2026, 11, 1]]}, "published-online": {"date-parts": [[2026, 10, 22]]}}
    unrelated = dict(good, DOI="10.9999/other", ISSN=["1111-1111"])
    def get(req):
        seen.append(req.url.params)
        return httpx.Response(200, json={"message": {"items": [good, unrelated]}})
    src = Sources(transport(get));src.fetched=0
    items = src._crossref_search(source, NOW - timedelta(days=7), NOW)
    assert len(items) == 1 and items[0].doi == doi and items[0].published_at == "2026-10-22T00:00:00Z"
    assert {p["query"] for p in seen} == set(SEARCH_TERMS)
    assert all(PUBLISHER_FILTERS[source] in p["filter"] for p in seen)
    assert all("from-pub-date:" in p["filter"] and p["sort"] == "indexed" for p in seen)


def test_url_dedupe_preserves_distinct_known_dois_and_published_semantics(engine):
    article = Record(source="acs", external_id="paper", kind="journal_article", title="Superconductivity",
                     url="https://pubs.acs.org/example", doi="10.1021/example", content_type="journal_article")
    with Session(engine) as db, db.begin():
        item = upsert(db, article, iso(NOW));id_ = item.id
        # 后来的预印本不能把已发表版本重新投影为预印本。
        upsert(db, replace(article, source="arxiv", external_id="preprint", kind="preprint", content_type="preprint"), iso(NOW))
        assert db.get(NewsFeedItem,id_).kind == "journal_article"
        upsert(db, replace(article, external_id="different", doi="10.1021/different"), iso(NOW))
        assert len(list(db.scalars(select(NewsFeedItem)))) == 2


def test_crossref_later_page_failure_keeps_first_page():
    entries = [{"DOI": f"10.1103/{i}", "type": "journal-article", "title": ["Superconductivity"]} for i in range(100)]
    def get(req):
        return httpx.Response(200, json={"message": {"items": entries, "next-cursor": "next"}}) if req.url.params["cursor"] == "*" else httpx.Response(403)
    src = Sources(transport(get));src.fetched=0
    assert len(src._crossref_search("crossref", NOW, NOW)) == 100
    assert src.partial_error == "access_denied"


def test_aggregator_cannot_turn_publisher_news_into_research(engine):
    news = Record(source="science", external_id="news", kind="news", content_type="research_report", discovery_source="science",
                  title="Superconductivity research report", url="https://www.science.org/doi/10.1126/science.example", doi="10.1126/science.example")
    with Session(engine) as db, db.begin():
        item_id = upsert(db, news, iso(NOW)).id
        for source in ["crossref", "openalex"]:
            upsert(db, replace(news, source=source, external_id=source, discovery_source=source, kind="journal_article", content_type="journal_article"), iso(NOW))
            item = db.get(NewsFeedItem, item_id)
            assert item.kind == item.display_kind == "news" and item.content_type == "research_report"

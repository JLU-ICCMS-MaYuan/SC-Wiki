"""#172：保留题录年份、来源身份和下载日期保护。"""
import pytest

from backend.ingest.publication_year import publication_evidence


def metadata(years=(2012, 2012)):
    return {'DOI': '10.1073/pnas.1118168109', 'title': ['Superconductive calcium hydride'],
            'published-online': {'date-parts': [[years[0], 4, 6]]},
            'published-print': {'date-parts': [[years[1], 4, 24]]}}


def test_publication_year_requires_doi_title_and_unambiguous_publication_dates():
    m = metadata()
    assert publication_evidence(m, m['DOI'], m['title'][0])['year'] == 2012
    assert publication_evidence(m, '10.9999/other', m['title'][0])['status'] == 'identity_mismatch'
    assert publication_evidence(m, m['DOI'], 'Another scientific paper')['status'] == 'identity_mismatch'
    assert publication_evidence(metadata((2012, 2013)), m['DOI'], m['title'][0])['status'] == 'ambiguous'
    m.pop('published-online');m.pop('published-print');m['created']={'date-parts':[[2021]]}
    assert publication_evidence(m, m['DOI'], m['title'][0])['status'] == 'unavailable'


def test_verified_publication_replaces_wrong_grobid_year_and_keeps_history():
    from backend.ingest.grobid_document import apply_bibliography
    m = metadata()
    doc = {'status': 'succeeded', 'file_id': 'main', 'source_sha256': 'a'*64, 'parser_version': '1',
           'metadata': {'doi': m['DOI'], 'title': m['title'][0], 'year': 2021},
           'metadata_sources': {'year': {'text': '2021-09-16'}}}
    draft = {'paper': {'year': 2012}}
    apply_bibliography(draft, doc, publication_verification={**publication_evidence(m, m['DOI'], m['title'][0]), 'source_sha256': 'a'*64})
    assert draft['paper']['year'] == 2012
    assert draft['bibliography_sources']['fields']['year']['text'] == '2021-09-16'
    assert any(c['field'] == 'year' and c['grobid_value'] == 2021 for c in draft['bibliography_conflicts'])
    assert doc['metadata']['year'] == 2021


@pytest.mark.parametrize('invalid', ['file', 'title', 'doi'])
def test_publication_proof_from_another_source_cannot_replace_year(invalid):
    from backend.ingest.grobid_document import apply_bibliography
    m = metadata()
    doc = {'status': 'succeeded', 'file_id': 'main', 'source_sha256': 'a'*64, 'parser_version': '1',
           'metadata': {'doi': m['DOI'], 'title': m['title'][0], 'year': 2021}, 'metadata_sources': {}}
    proof = {**publication_evidence(m, m['DOI'], m['title'][0]), 'source_sha256': 'a'*64}
    proof[{'file': 'source_sha256', 'title': 'title', 'doi': 'doi'}[invalid]] = 'another source'
    draft = {'paper': {}}
    apply_bibliography(draft, doc, publication_verification=proof)
    assert draft['paper']['year'] == 2021
    assert draft['bibliography_sources']['fields']['year']['publication_verification']['status'] == 'identity_mismatch'


def test_pdf_doi_fallback_and_download_date_require_matching_original(tmp_path):
    import hashlib
    import pymupdf
    from backend.ingest.publication_year import verify_document_year
    m = metadata()
    path = tmp_path / 'original.pdf'
    with pymupdf.open() as pdf:
        page = pdf.new_page()
        page.insert_text((40, 40), m['DOI'] + '\nDownloaded by guest on September 16, 2021')
        pdf.save(path)
    doc = {'metadata': {'title': m['title'][0], 'year': 2021},
           'source_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
           'metadata_sources': {'year': {'text': '2021-09-16'}}}
    calls = []
    def lookup(doi, title):
        calls.append((doi, title))
        return publication_evidence(m, doi, title)
    result = verify_document_year(doc, {'year': 2021, 'doi': m['DOI']}, source_pdf=path, lookup=lookup)
    assert result['status'] == 'verified'
    assert result['download_date_match']['date'] == '2021-09-16'
    assert result['doi_source']['kind'] == 'pdf_text_layer'
    assert len(calls) == 1
    changed = verify_document_year({**doc, 'source_sha256': 'wrong'}, {'year': 2012}, source_pdf=path, lookup=lookup)
    assert changed['status'] == 'identity_mismatch'
    missing = verify_document_year(doc, {'year': 2012}, source_pdf=tmp_path/'missing.pdf', lookup=lookup)
    assert missing['status'] == 'unavailable'
    assert len(calls) == 1

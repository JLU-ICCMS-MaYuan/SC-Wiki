"""#172：差异分流不能以格式清洗隐藏科学变化。"""
from copy import deepcopy
from types import SimpleNamespace

import pytest

from backend.ingest.parsing_diagnostics import notation_key, annotate_differences
from backend.ingest.publication_year import publication_evidence


def region(a, b, kind='paragraph'):
    return {'file_id': 'main', 'pdf_page': 1, 'kind': kind, 'anchor': 'a', 'selected': 'a',
            'engine': 'mineru', 'selected_text': a,
            'alternatives': [{'block_id': 'b', 'engine': 'marker', 'text': b, 'bbox': [10, 10, 200, 100]}]}


@pytest.mark.parametrize('a,b', [(r'\mathrm { C a H } _ { 2 }', 'CaH₂'),
    ('electron–phonon coupling.', 'electron-phonon  coupling.'), (r'\mu ^ { * }', 'μ*')])
def test_bounded_notation_equivalence(a, b):
    assert notation_key(a) == notation_key(b)


@pytest.mark.parametrize('a,b', [('μ*', 'μ'), ('H₄²⁻', 'H₄²⁺'), ('P-1', 'P1'),
    ('235 K', '220 K'), ('1 meV', '1 eV'), ('m3m', 'm3̄m'), ('cI14', 'cl14')])
def test_meaningful_symbols_are_never_erased(a, b):
    assert notation_key(a) != notation_key(b)
    result = annotate_differences({'parsing_conflicts': [region(a, b)]}, {}, [])
    assert result['parsing_conflicts'][0]['triage']['status'] != 'system_checked'


def test_census_keeps_raw_text_and_stable_region_identity():
    raw = {'parsing_conflicts': [region(r'\mathrm{CaH}_{2}', 'CaH2'), region('μ*', 'μ')],
           'material_states': []}
    raw['parsing_conflicts'][1]['selected'] = 'c'
    before = deepcopy(raw)
    a = annotate_differences(raw, {}, [])
    b = annotate_differences({**raw, 'parsing_conflicts': list(reversed(raw['parsing_conflicts']))}, {}, [])
    assert raw == before
    assert {r['triage']['id'] for r in a['parsing_conflicts']} == {r['triage']['id'] for r in b['parsing_conflicts']}
    assert a['parsing_conflicts'][1]['triage']['impact']['status'] == 'unmapped'


def test_same_numbers_without_cell_alignment_are_not_table_verification():
    r = region('H1 0.1 0.2 H2 0.3 0.4', 'H2 0.1 0.2 H1 0.3 0.4', 'table')
    result = annotate_differences({'parsing_conflicts': [r]}, {}, [])
    assert result['parsing_conflicts'][0]['triage']['category'] == 'table'
    assert result['parsing_conflicts'][0]['triage']['status'] == 'system_pending'


def test_same_flattened_table_with_swapped_cell_positions_still_needs_checking():
    cells = lambda swapped: [SimpleNamespace(row_index=0, column_index=1 if swapped else 0, text='H1', block_id=None),
                             SimpleNamespace(row_index=0, column_index=0 if swapped else 1, text='0.1', block_id=None)]
    ir = SimpleNamespace(blocks=[], pages=[], source_sha256='a'*64, tables=[
        SimpleNamespace(block_id='a', row_count=1, column_count=2, cells=cells(False)),
        SimpleNamespace(block_id='b', row_count=1, column_count=2, cells=cells(True))])
    result = annotate_differences({'parsing_conflicts':[region('H1 0.1','H1 0.1','table')]}, {'main':ir}, [])
    assert result['parsing_conflicts'][0]['triage']['status']=='system_pending'


def test_spaced_digits_are_only_a_notation_candidate_not_equivalence():
    item=annotate_differences({'parsing_conflicts':[region('at 1 0 0 GPa','at 100 GPa')]},{},[])['parsing_conflicts'][0]
    assert item['triage']['category']=='notation'
    assert item['triage']['status']=='system_pending'


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


def test_unreadable_original_keeps_equivalent_text_pending(tmp_path):
    from backend.ingest.parsing_diagnostics import read_pdf_regions
    ir = SimpleNamespace(source_sha256='a'*64, pages=[SimpleNamespace(pdf_page=1)], blocks=[])
    originals = read_pdf_regions({'main': ir}, {'main': tmp_path/'missing.pdf'})
    item = annotate_differences({'parsing_conflicts': [region('same', 'same')]}, {'main': ir}, [], pdf_regions=originals)['parsing_conflicts'][0]
    assert item['triage']['status'] == 'system_pending'
    assert item['triage']['reason'] == 'original_unavailable'


def test_empty_or_duplicate_table_cells_cannot_be_verified():
    from backend.ingest.parsing_diagnostics import _grid
    assert _grid(SimpleNamespace(cells=[], row_count=1, column_count=1), {}) is None
    cell = SimpleNamespace(row_index=0, column_index=0, text='H1', block_id=None)
    assert _grid(SimpleNamespace(cells=[cell, cell], row_count=1, column_count=1), {}) is None

"""#225：真实书目身份、模型协议和持久复用，不以主题相似作为引用事实。"""
import json
from pathlib import Path

import pytest

from backend.services.citation_matching import CitationCatalog, match_references, source_signature


FIXTURES = Path(__file__).resolve().parents[2] / 'docs/specs/225-citation-matching-and-static-graph/assets'


def corpus():
    return json.loads((FIXTURES / 'citation-corpus.json').read_text())


def test_original_four_paper_corpus_recovers_six_real_edges_without_model():
    data = corpus()
    expected = {r['reference_id']: r['paper_id'] for r in
                json.loads((FIXTURES / 'reference-audit.json').read_text())['labels']}
    catalog = CitationCatalog(data['papers'])
    found = {}
    for ref in data['references']:
        decision = catalog.decide(ref, exclude_id=ref['paper_id'])
        if decision['paper_id'] is not None:
            found[ref['id']] = decision['paper_id']
    assert found == {k: v for k, v in expected.items() if v is not None}
    for reference_id in (307, 1265, 296, 301):
        ref = next(r for r in data['references'] if r['id'] == reference_id)
        assert catalog.decide(ref, exclude_id=ref['paper_id'])['paper_id'] is None


def test_distinct_formula_counts_and_author_year_conflicts_are_not_erased():
    catalog = CitationCatalog([{'id': 1, 'title': 'Superconductivity in LaH10',
                               'year': 2017, 'authors': ['Hanyu Liu'], 'doi': None}])
    for title, year, authors in [('Superconductivity in LaH 9', 2017, ['H Liu']),
                                 ('Superconductivity in LaH10', 2024, ['H Liu']),
                                 ('Superconductivity in LaH10', 2017, ['F Peng'])]:
        assert catalog.decide({'title': title, 'year': year, 'authors': authors})['paper_id'] is None


def test_model_only_receives_uncertain_candidates_and_reuses_completed_decision():
    catalog = CitationCatalog([{'id': 9, 'title': 'Superconductivity in compressed hydrogen cages',
                               'year': 2017, 'authors': ['Hanyu Liu'], 'doi': None}])
    refs = [{'reference_index': 0, 'raw_citation': 'H Liu (2017), Superconductivity in compressed hydrogen cages.',
             'title': 'Superconductivity of compressed hydrogen cages', 'authors': ['H Liu'], 'year': 2017}]
    calls, cache = [], {}
    def model(system, user, **kwargs):
        payload = json.loads(user)
        calls.append(payload)
        return {'matches': {'0': {'paper_id': 9, 'reason': '原引文、作者和年份对应'}}}
    first = match_references(refs, catalog, namespace='upload:test', model=model,
                             cache_get=cache.get, cache_put=cache.__setitem__)
    assert first[0]['paper_id'] == 9 and first[0]['method'] == 'llm2'
    second = match_references(refs, catalog, namespace='upload:test', model=model,
                              cache_get=cache.get, cache_put=cache.__setitem__)
    assert second == first and len(calls) == 1
    catalog_changed = CitationCatalog([{'id': 9, 'title': 'Superconductivity in compressed hydrogen cages',
                                       'year': 2017, 'authors': ['Hanyu Liu'], 'doi': None, 'content_revision': 2}])
    match_references(refs, catalog_changed, namespace='upload:test', model=model,
                      cache_get=cache.get, cache_put=cache.__setitem__)
    assert len(calls) == 1
    catalog_changed = CitationCatalog([{'id': 9, 'title': 'Superconductivity in compressed hydrogen cages: revised',
                                       'year': 2017, 'authors': ['Hanyu Liu'], 'doi': None, 'content_revision': 2}])
    match_references(refs, catalog_changed, namespace='upload:test', model=model,
                      cache_get=cache.get, cache_put=cache.__setitem__)
    assert len(calls) == 2


@pytest.mark.parametrize('answer', [
    {'matches': {}},
    {'matches': {'0': {'paper_id': 308, 'reason': '主题相关'}}},
    {'matches': {'0': {'paper_id': 9, 'reason': '一样'}, '1': {'paper_id': 9, 'reason': '多答'}}},
])
def test_illegal_model_result_is_retained_as_failure_and_not_silently_repaired(answer):
    catalog = CitationCatalog([{'id': 9, 'title': 'Superconductivity in compressed hydrogen cages',
                               'year': 2017, 'authors': ['H Liu']}])
    refs = [{'reference_index': 0, 'raw_citation': 'H Liu (2017) Superconductivity in compressed hydrogen cages',
             'title': 'Superconductivity of compressed hydrogen cages', 'year': 2017, 'authors': ['H Liu']}]
    cache = {}
    with pytest.raises(ValueError):
        match_references(refs, catalog, namespace='bad', model=lambda *a, **k: answer,
                          cache_get=cache.get, cache_put=cache.__setitem__)
    assert any(v.get('state') == 'failed' and v.get('response') == answer for v in cache.values())


def test_signature_tracks_bibliography_and_identity_but_not_other_form_fields():
    draft = {'paper': {'title': 'A', 'year': 2024}, 'citation_extraction': {'references': []},
             'material_states': [{'label': 'original'}]}
    first = source_signature(draft)
    draft['material_states'][0]['label'] = 'edited'
    assert source_signature(draft) == first
    draft['paper']['title'] = 'B'
    assert source_signature(draft) != first


def test_browser_payload_cannot_replace_or_drop_program_owned_matching_result():
    from backend.services.citation_matching import preserve_matching_snapshot
    previous = {'citation_matching': {'version': 'server', 'references': [{'matched': True}]}}
    updated = {'paper': {'title': 'Edited'}, 'citation_matching': {'version': 'forged'}}
    preserve_matching_snapshot(updated, previous)
    assert updated['citation_matching'] == previous['citation_matching']
    updated['citation_matching']['references'].clear()
    assert previous['citation_matching']['references']
    preserve_matching_snapshot(updated, {})
    assert 'citation_matching' not in updated


def test_missing_title_or_conflicting_extracted_metadata_goes_to_model_not_auto_match():
    catalog = CitationCatalog([{'id': 9, 'title': 'Superconductivity in compressed hydrogen cages',
                               'year': 2017, 'authors': ['Hanyu Liu']}])
    refs = [
        {'reference_index': 0, 'title': None, 'raw_citation':
            'H Liu (2017) Superconductivity in compressed hydrogen cages', 'year': 2017, 'authors': ['H Liu']},
        {'reference_index': 1, 'title': 'Superconductivity in compressed hydrogen cages',
         'raw_citation': 'H Liu (2017) Superconductivity in compressed hydrogen cages',
         'year': 2018, 'authors': ['F Peng']},
    ]
    assert all(catalog.decide(r)['paper_id'] is None for r in refs)
    seen = []
    def model(system, user, **kwargs):
        data = json.loads(user);seen.extend(data['references'])
        return {'matches': {str(i): {'paper_id': 9, 'reason': '原始引文支持，提取提示不完整'} for i in (0, 1)}}
    result = match_references(refs, catalog, namespace='raw-fallback', model=model)
    assert [r['paper_id'] for r in result] == [9, 9]
    assert len(seen) == 2 and seen[0]['reference']['raw_citation'] == refs[0]['raw_citation']

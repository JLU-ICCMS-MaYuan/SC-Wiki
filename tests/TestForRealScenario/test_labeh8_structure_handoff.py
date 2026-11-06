"""真实原页响应：已识别的独立位点须进入既有对称展开，冲突不放行。"""
import json
from copy import deepcopy
from pathlib import Path

import pytest


def fixture():
    return json.loads((Path(__file__).parent / 'fixtures/labeh8-structure-reading.json').read_text())


def replay(data):
    from backend.ingest.structure_reading import _candidates
    return _candidates(data['answer'], data['catalog'], set(data['imaged_pages']), data['source'])


def test_actual_reported_labeh8_sites_expand_with_original_rows_and_derived_label():
    from backend.services.structure_candidates import read_atoms
    data = fixture()
    result = replay(data)
    first = result[0]
    assert first['status'] == 'valid', first['validation']['message']
    assert len(read_atoms('cif', first['representations']['conventional']['cif']['text'])) == 40
    assert first['derivation']['kind'] == 'space_group_expansion'
    assert set(first['derivation']['inferred_cell_parameters']) == {'alpha', 'beta', 'gamma'}
    assert first['reported_structure']['atomic_positions'] == data['answer']['structures'][0]['atoms']
    assert all(s['quote'] in {r['content'] for r in data['catalog'].values()} for s in first['sources'])
    # 原文LaAlH8实际写B，不能借相邻结构或改成Al来生成模型。
    assert result[2]['status'] == 'blocked'


@pytest.mark.parametrize('fault', ['coordinates', 'material', 'no_image', 'wrong_group'])
def test_real_neighbor_conflicts_cannot_pass_by_using_symmetry(fault):
    data = deepcopy(fixture())
    data['answer']['structures'] = data['answer']['structures'][:1]
    item = data['answer']['structures'][0]
    if fault == 'coordinates':
        item['atoms'][0]['coordinates'][0] = .4
    elif fault == 'material':
        item['material'] = 'LaBH8'
    elif fault == 'no_image':
        data['imaged_pages'] = []
    else:
        item['space_group_symbol'] = 'Pm-3m'
    assert replay(data)[0]['status'] == 'blocked'

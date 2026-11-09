"""逐页盘点与逐图读取不能依赖解析器已经找全图片。"""
import json

import pytest

from backend.ingest.chart_reading import page_inventory, ChartReadingError


def test_inventory_keeps_two_figures_separate_and_finds_unindexed_page():
    answer = {'pages': [
        {'page': 1, 'figures': [
            {'bbox': [0, 0, 500, 500], 'label': 'Fig 1', 'target': True, 'reason': 'Tc'},
            {'bbox': [500, 0, 1000, 500], 'label': 'Fig 2', 'target': True, 'reason': 'DOS'}]},
        {'page': 2, 'figures': [
            {'bbox': [0, 0, 1000, 1000], 'label': 'Fig S1', 'target': True, 'reason': 'omega_log'}]}]}
    targets, excluded = page_inventory(answer, {1: (200, 400), 2: (100, 300)})
    assert len(targets) == 3 and not excluded
    assert targets[0]['bbox'] == [0, 0, 100, 200]
    assert targets[1]['bbox'] == [100, 0, 200, 200]
    assert targets[2]['page'] == 2
    assert len({r['region_id'] for r in targets}) == 3


def test_inventory_cannot_claim_completion_without_every_page():
    with pytest.raises(ChartReadingError, match='页面'):
        page_inventory({'pages': [{'page': 1, 'figures': []}]}, {1: (200, 400), 2: (200, 400)})


def test_inventory_rejects_invalid_or_duplicate_regions():
    figure = {'bbox': [10, 20, 400, 300], 'label': 'a', 'target': True, 'reason': 'Tc'}
    with pytest.raises(ChartReadingError):
        page_inventory({'pages': [{'page': 1, 'figures': [figure, figure]}]}, {1: (200, 400)})


def test_shared_caption_does_not_make_duplicate_non_target_rectangles_valid():
    figures = [{'bbox': [98, 593, 910, 897], 'label': f'Fig S11({panel})',
                'target': False, 'reason': '结构示意图，无受支持标量'} for panel in ('a', 'b')]
    with pytest.raises(ChartReadingError):
        page_inventory({'pages': [{'page': 11, 'figures': figures}]}, {11: (600, 800)})
    targets, excluded = page_inventory({'pages': [{'page': 11, 'figures': [{
        **figures[0], 'label': 'Fig S11(a,b)', 'reason': '两幅结构示意共用图注，无受支持标量'}]}]},
        {11: (600, 800)})
    assert not targets and len(excluded) == 1
    assert excluded[0]['label'] == 'Fig S11(a,b)'

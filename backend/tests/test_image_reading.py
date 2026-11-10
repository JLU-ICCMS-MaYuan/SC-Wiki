"""真实原PDF上的封闭工具、回执/像素和定向重读。"""
import json

import pytest

from backend.tests.test_pdf_regions import source
from backend.ingest.image_reading import ImageReadingTools


def tools(tmp_path):
    path, ir = source(tmp_path)
    tool = ImageReadingTools({'main': ir}, {'main': path}, cache_dir=tmp_path / 'cache')
    return tool, path, ir


def test_complete_then_adjust_returns_same_source_pixels_and_version(tmp_path):
    tool, path, ir = tools(tmp_path)
    full, images = tool.call('read_complete_object', {'file_id': 'main', 'block_id': 'fig'})
    assert len(images) == 1 and images[0].startswith('data:image/png;base64,')
    assert full['locator']['caption_status'] == 'located' and full['images'][0]['dpi'] == 600
    child, pixels = tool.call('adjust_image_region', {'region_id': full['locator']['region_id'],
        'bbox_page': [30, 80, 100, 180], 'reason': 'ScH6 bar localization', 'dpi': 600})
    assert child['parent_receipt_id'] == full['receipt_id']
    assert child['locator']['parent_region_id'] == full['locator']['region_id']
    assert child['source_sha256'] == ir.source_sha256 and child['images'][0]['image_sha256'] != full['images'][0]['image_sha256']
    assert full['receipt_id'] in tool.receipts and pixels
    assert 'data:image' not in json.dumps(tool.state())
    json.loads(json.dumps(ir.model_dump(mode='json')))


def test_text_recognition_is_located_and_has_real_method(tmp_path):
    tool, path, ir = tools(tmp_path)
    full, _ = tool.call('read_complete_object', {'file_id': 'main', 'block_id': 'fig'})
    result, images = tool.call('recognize_image_text', {'region_id': full['locator']['region_id']})
    assert any('ScH6' in word['text'] for word in result['text_observations'])
    assert all(len(word['bbox_page']) == 4 for word in result['text_observations'])
    assert result['reader']['method'] == 'pdf_text_and_registered_ocr'
    assert images


def test_wrong_source_unknown_arguments_and_forged_locator_are_refused(tmp_path):
    tool, path, ir = tools(tmp_path)
    for args in [{'file_id': 'other', 'block_id': 'fig'}, {'file_id': 'main', 'block_id': 'fig', 'path': '/etc/passwd'}]:
        with pytest.raises(ValueError): tool.call('read_complete_object', args)
    with pytest.raises(ValueError):
        tool.call('adjust_image_region', {'region_id': 'made-up', 'bbox_page': [0,0,100,100], 'reason': 'guess', 'dpi':600})


def test_action_without_new_evidence_is_not_repeated_forever(tmp_path):
    tool, path, ir = tools(tmp_path)
    args = {'file_id': 'main', 'block_id': 'fig'}
    first, images = tool.call('read_complete_object', args)
    again, second_images = tool.call('read_complete_object', args)
    assert again['receipt_id'] == first['receipt_id'] and again['reused']
    assert again['progress'] == 'no_new_evidence'
    assert second_images == images


def test_restored_tool_can_rebuild_image_without_changing_observations(tmp_path):
    tool, path, ir = tools(tmp_path)
    result, images = tool.call('read_complete_object', {'file_id':'main','block_id':'fig'})
    saved = json.loads(json.dumps(tool.state()))
    for p in (tmp_path/'cache').iterdir():p.unlink()
    restored = ImageReadingTools({'main':ir},{'main':path},state=saved,cache_dir=tmp_path/'cache')
    again, pixels = restored.call('recognize_image_text', {'region_id':result['locator']['region_id']})
    assert pixels == images and again['source_sha256'] == result['source_sha256']


def test_unchanged_crop_is_not_a_new_region_chain(tmp_path):
    tool, _, _ = tools(tmp_path)
    full, pixels = tool.call('read_complete_object',{'file_id':'main','block_id':'fig'})
    adjusted, actual = tool.call('adjust_image_region',{'region_id':full['locator']['region_id'],
        'bbox_page':full['locator']['bbox_page'],'dpi':600,'reason':'检查相同边界'})
    assert adjusted['locator']['region_id'] == full['locator']['region_id']
    assert adjusted['images'][0]['image_sha256'] == full['images'][0]['image_sha256']
    assert actual == pixels

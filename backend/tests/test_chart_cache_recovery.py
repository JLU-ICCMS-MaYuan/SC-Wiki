"""独立面板裁剪及旧派生重复块的有界恢复，不放宽原始IR校验。"""
from copy import deepcopy
import io
import json

from PIL import Image
import pymupdf
import pytest

from backend.ingest.chart_reading import _chart_image, enrich_document
from backend.ingest.document_ir import DocumentIR, content_hash
from backend.tests.test_chart_reading import original, panel


def test_partial_panel_cannot_expand_to_whole_embedded_figure(tmp_path):
    pdf = pymupdf.open(); page = pdf.new_page(width=200, height=200)
    image = Image.new('RGB', (160, 160), 'red'); buf = io.BytesIO(); image.save(buf, format='PNG')
    page.insert_image((20, 20, 180, 180), stream=buf.getvalue())
    crop = [20, 20, 180, 70]
    actual, png, origin = _chart_image(pdf, page, [{'bbox': crop}], crop)
    assert actual == crop
    assert origin['image_kind'] == 'original_page_region'
    assert Image.open(io.BytesIO(png)).width > Image.open(io.BytesIO(png)).height * 3
    actual, _, origin = _chart_image(pdf, page, [{'bbox': [20, 20, 180, 180]}], [10, 10, 190, 190])
    assert actual == [10, 10, 190, 190] and origin['image_kind'] == 'original_page_region'
    assert origin['render_dpi'] == 600 and origin['native_sha256']
    pdf.close()


def repeated_notes(tmp_path):
    path, ir, source = original(tmp_path)
    def model(_prompt, content, **_options):
        if 'image_pages' in json.loads(content):
            return {'pages': [{'page': 1, 'figures': [
                {'bbox': [100, 100, 900, 450], 'label': 'top', 'target': True, 'reason': 'Tc'},
                {'bbox': [100, 550, 900, 900], 'label': 'bottom', 'target': True, 'reason': 'Tc'}]}]}
        return {'panels': [], 'notes': [{'scope':'target','reason':'无法读取，不能假设为零'}] * 2}
    enrich_document(ir, path, source, model)
    return path, ir, source


def test_identical_unresolved_notes_roundtrip_once(tmp_path):
    _, ir, _ = repeated_notes(tmp_path)
    restored = DocumentIR.model_validate_json(ir.model_dump_json())
    notes = [b for b in restored.blocks if 'chart_unresolved' in b.metadata]
    assert len(notes) == 2 and all('不能假设为零' in b.text for b in notes)
    assert len({b.metadata['chart_unresolved']['region_id'] for b in notes}) == 2
    assert len(restored.coverage['chart_reading']['unresolved']) == 4  # 每次原回执仍在


def legacy_cache(tmp_path):
    _, ir, _ = repeated_notes(tmp_path)
    data = ir.model_dump(mode='json')
    block = next(b for b in data['blocks'] if 'chart_unresolved' in b['metadata'])
    block['metadata']['parser'] = 'scientific-chart-reading-v2'
    data['coverage']['chart_reading']['version'] = 'scientific-chart-reading-v2'
    data['blocks'] = [b for b in data['blocks'] if b['block_id'] != block['block_id']] + [block]
    data['blocks'].append({**deepcopy(block), 'reading_order': 999})
    path = tmp_path / 'cached.json'; path.write_text(json.dumps(data, ensure_ascii=False))
    return path, data


def test_legacy_recovery_preserves_original_bytes_and_records_each_duplicate(tmp_path):
    from backend.ingest.chart_cache import load_document_ir
    path, data = legacy_cache(tmp_path); before = path.read_bytes()
    with pytest.raises(ValueError, match='重复 block_id'):
        DocumentIR.model_validate(data)
    restored = load_document_ir(path)
    assert len(restored.blocks) == len(data['blocks']) - 1
    assert path.with_name(path.name + '.before-chart-recovery').read_bytes() == before
    audit = json.loads(path.with_name(path.name + '.chart-recovery.json').read_text())
    assert len(audit['duplicates']) == 1 and audit['duplicates'][0]['discarded_reading_order'] == 999
    assert load_document_ir(path).model_dump() == restored.model_dump()


@pytest.mark.parametrize('change', ['text', 'source', 'original', 'version'])
def test_recovery_rejects_conflicting_or_non_chart_duplicates(tmp_path, change):
    from backend.ingest.chart_cache import load_document_ir
    path, data = legacy_cache(tmp_path)
    if change == 'text': data['blocks'][-1]['text'] += ' conflict'
    elif change == 'source': data['source_sha256'] = '0' * 64
    elif change == 'original':
        for b in data['blocks'][-2:]: b['metadata'] = {}
    elif change == 'version': data['coverage']['chart_reading']['version'] = 'future'
    path.write_text(json.dumps(data)); before = path.read_bytes()
    with pytest.raises(ValueError): load_document_ir(path)
    assert path.read_bytes() == before
    assert not path.with_name(path.name + '.before-chart-recovery').exists()


def test_new_version_retains_old_blocks_but_only_reads_current_facts(tmp_path):
    path, ir, source = original(tmp_path)
    from backend.tests.test_chart_reading import fake_model
    enrich_document(ir, path, source, fake_model([]))
    old = next(b for b in ir.blocks if 'chart_reading' in b.metadata)
    old.metadata['parser'] = 'scientific-chart-reading-v2'
    ir.coverage['chart_reading']['version'] = 'scientific-chart-reading-v2'
    enrich_document(ir, path, source, fake_model([]))
    retained = ir.block(old.block_id)
    assert retained.text == old.text and retained.content_hash == old.content_hash
    assert retained.metadata['selected_for_reading'] is False
    assert retained.metadata['superseded_by'] == ir.coverage['chart_reading']['version']
    DocumentIR.model_validate_json(ir.model_dump_json())


def test_save_rejects_duplicate_before_overwriting_valid_artifact(tmp_path, monkeypatch):
    from backend.ingest import upload_jobs
    _, ir, _ = original(tmp_path)
    monkeypatch.setattr(upload_jobs, 'artifact_directory', lambda _: tmp_path / 'artifacts')
    upload_jobs._save_document_ir('task', 'main', ir)
    path = tmp_path / 'artifacts/document_ir/main.json'; before = path.read_bytes()
    ir.blocks.append(ir.blocks[0].model_copy(deep=True))
    with pytest.raises(ValueError, match='重复 block_id'):
        upload_jobs._save_document_ir('task', 'main', ir)
    assert path.read_bytes() == before

"""#227：真实PDF图像、完整图表协议及正式提取入口的隔离验证。"""
from copy import deepcopy
import base64
import hashlib
import json
from types import SimpleNamespace

import pymupdf
import pytest

from backend.ingest.chart_reading import enrich_document, calibrate_panel, ChartReadingError
from backend.ingest.document_ir import DocumentIR, DocumentBlock, PageGeometry, content_hash


def test_horizontal_scalar_role_never_turns_vertical_frequency_into_lambda():
    from PIL import Image
    from backend.ingest.chart_reading import reading_schema
    from backend.rag.structured_output import validate_output
    value=panel();value.update(kind='line',quantity='lambda_ep',quantity_name='Total coupling',unit='dimensionless',
        axis={'scale':'linear','bounds':[100,900],'ticks':[{'position':100,'value':2000},{'position':900,'value':0}]},
        x_axis={'scale':'linear','bounds':[100,900],'ticks':[{'position':100,'value':0},{'position':900,'value':4}]},
        x_quantity='other',x_unit='dimensionless',value_coordinate='x')
    value['points']=value['points'][:1];value['series']=[value['points'][0]['series']]
    value['points'][0].update(x=900,y=100)
    validate_output({'panels':[value],'notes':[]},reading_schema())
    readings,issues=calibrate_panel(value,Image.new('RGB',(1000,1000),'white'),
        {'file_id':'source','sha256':'a'*64,'page':1},[0,0,100,100])
    assert not issues and readings[0]['value_number']==4
    assert readings[0]['value_coordinate']=='x'


def original(tmp_path):
    path = tmp_path / 'source.pdf'
    pdf = pymupdf.open(); page = pdf.new_page(width=200, height=200)
    page.insert_text((4, 12), 'YH10 400 GPa, two Tc series in the original plot.', fontsize=5)
    page.draw_line((25, 26.4), (25, 173.6))
    page.insert_text((8, 28), '200', fontsize=5); page.insert_text((10, 174), '0', fontsize=5)
    page.draw_rect((75, 100, 90, 173.6), fill=(0, 0, 1))
    page.draw_rect((110, 63.2, 125, 173.6), fill=(0, 1, 0))
    pdf.save(path); pdf.close()
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    ir = DocumentIR(document_id='test', source_file_id='main', source_sha256=sha,
        parse_profile='complementary', pages=[PageGeometry(pdf_page=1, width=200, height=200)],
        blocks=[DocumentBlock(block_id='body', block_type='paragraph', pdf_page=1, reading_order=0,
            text='Fig. 1: YH10 at 400 GPa. Blue: mu*=0.13; green: mu*=0.1.', content_hash=content_hash('body')),
            DocumentBlock(block_id='figure', block_type='figure', pdf_page=1, reading_order=1,
                bbox=(20, 20, 180, 180), content_hash=content_hash('figure'))])
    return path, ir, {'file_id': 'main', 'sha256': sha, 'filename': 'source.pdf', 'role': 'main'}


def panel(kind='bar'):
    def point(series, x, y, mu):
        return {'category': 'YH10', 'series': series, 'material': 'YH10', 'pressure_value_gpa': 400,
            'space_group_symbol': None, 'mu_star': mu, 'method_raw': None, 'reading': 'position',
            'x': x, 'y': y, 'label_value': None, 'label_text': None, 'pixel_error': 1,
            'conditions': [], 'reason': '图注和蓝/绿图例明确独立系列与压力'}
    return {'figure': 'Fig. 1', 'panel': 'Tc', 'kind': kind, 'quantity': 'tc', 'quantity_name': 'Tc', 'unit': 'K',
        'layout': 'matrix', 'categories': ['YH10'], 'series': ['blue', 'green'],
        'axis': {'scale': 'linear', 'bounds': [100, 900],
                 'ticks': [{'position': 100, 'value': 200}, {'position': 900, 'value': 0}]},
        'x_axis': None, 'x_quantity': None, 'x_unit': None,
        'colorbar': None, 'points': [point('blue', 405, 500, 0.13), point('green', 595, 300, 0.1)],
        'unresolved': [], 'reason': '两根柱分别有图例，未将正文最高值广播'}


def fake_model(calls):
    def model(prompt, content, **options):
        data = json.loads(content); calls.append(data)
        assert all(base64.b64decode(x.split(',', 1)[1]).startswith(b'\x89PNG') for x in options['images'])
        if 'regions' in data:
            return {'pages': [{'page': p, 'figures': [{'bbox': [100, 100, 900, 900],
                'label': 'Fig 1', 'target': True, 'reason': 'Tc柱状图'}]} for p in data['image_pages']]}
        assert len(options['images']) == 2
        return {'panels': [panel()], 'notes': []}
    return model


@pytest.mark.parametrize('reverse_bounds', [False, True])
def test_native_images_calibration_and_ir_roundtrip_keep_each_series(tmp_path, reverse_bounds):
    path, ir, source = original(tmp_path); calls = []; original_blocks = deepcopy(ir.blocks)
    model = fake_model(calls)
    def read(prompt, content, **options):
        answer = model(prompt, content, **options)
        if reverse_bounds:
            for value in answer.get('panels', []):
                value['axis']['bounds'].reverse()
        return answer
    report = enrich_document(ir, path, source, read)
    assert len(calls) == 2 and report['readings'] == 2
    assert ir.blocks[:2] == original_blocks
    restored = DocumentIR.model_validate_json(ir.model_dump_json())
    values = [b.metadata['chart_reading'] for b in restored.blocks if 'chart_reading' in b.metadata]
    for reading, expected in zip(values, [100, 150]):
        assert abs(reading['value_number'] - expected) <= reading['reading_precision']
    assert [v['point']['mu_star'] for v in values] == [0.13, 0.1]
    assert all(v['reading_precision'] > 0 and v['value_raw'].startswith('~') for v in values)
    assert all(v['source_sha256'] == source['sha256'] for v in values)
    assert all('NOT physical measurement error' in b.text for b in restored.blocks[2:])
    assert enrich_document(ir, path, source, fake_model(calls)) == report and len(calls) == 2


def test_old_completed_chart_reading_is_reprocessed_after_axis_fix(tmp_path):
    path, ir, source = original(tmp_path); calls = []
    ir.coverage['chart_reading'] = {'version': 'scientific-chart-reading-v3',
        'status': 'completed', 'readings': 0, 'unresolved': [{'reason': '坐标边界反序'}]}
    report = enrich_document(ir, path, source, fake_model(calls))
    assert len(calls) == 2 and report['readings'] == 2
    assert report['version'] != 'scientific-chart-reading-v3'


def test_graph_precision_and_original_locator_survive_transaction_and_reread(tmp_path):
    import asyncio
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from backend import models
    from backend.database import Base
    from backend.ingest.document_storage import persist_document, link_document_evidence
    from backend.ingest.document_regions import render_region
    path, ir, source = original(tmp_path)
    enrich_document(ir, path, source, fake_model([]))
    ir.parser = {'name': 'calibration-fixture', 'version': '1', 'mode': 'ocr'}
    block = next(b for b in ir.blocks if 'chart_reading' in b.metadata)
    before = path.read_bytes()
    async def run():
        engine = create_async_engine('sqlite+aiosqlite:///:memory:')
        async with engine.begin() as connection: await connection.run_sync(Base.metadata.create_all)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as session, session.begin():
            paper = models.Paper(year=2026, content_revision=1, review_status='pending')
            session.add(paper); await session.flush()
            file = models.PaperFile(paper_id=paper.id, paper_revision=1, role='main', sort_order=0,
                original_filename=path.name, stored_path='fixture/source.pdf', sha256=source['sha256'], size=path.stat().st_size)
            session.add(file); await session.flush()
            parser, blocks = await persist_document(session, paper, file, ir)
            chunk = models.PaperChunk(paper_id=paper.id, paper_revision=1, paper_file_id=file.id, chunk_index=0, content=block.text)
            session.add(chunk); await session.flush()
            evidence = models.PaperEvidence(paper_id=paper.id, paper_revision=1, paper_chunk_id=chunk.id,
                field_path='value_number', quote=block.text, page_start=1, page_end=1)
            session.add(evidence); await session.flush()
            locator = await link_document_evidence(session, evidence, chunk, parser, blocks, block_id=block.block_id)
            assert locator and locator.source_kind == 'vision'
            file_id = file.id
        async with factory() as session:
            saved = await session.scalar(select(models.PaperDocumentBlock).where(models.PaperDocumentBlock.block_id == block.block_id))
            assert saved.metadata_json['chart_reading'] == block.metadata['chart_reading']
            saved_run = await session.scalar(select(models.PaperDocumentParserRun))
            assert saved_run.document_json['source_file_id'] == str(file_id)
            restored = DocumentIR.model_validate(saved_run.document_json)
            crop = render_region(restored, path, source['sha256'], quote=block.text, pdf_page=1)
            assert crop['status'] == 'located' and crop['image'].startswith('data:image/')
        await engine.dispose()
    asyncio.run(run())
    assert path.read_bytes() == before


def test_matrix_cannot_silently_drop_a_series(tmp_path):
    from PIL import Image
    p = panel(); p['points'].pop()
    with pytest.raises(ChartReadingError, match='未说明去向'):
        calibrate_panel(p, Image.new('RGB', (200, 200)), {'file_id': 'main', 'sha256': 'a' * 64, 'page': 1}, [0, 0, 200, 200])


def test_line_keeps_multiple_pressure_points_in_same_material_and_series():
    from PIL import Image
    p = panel('line'); p['layout'] = 'sparse'; p['series'] = ['blue']
    p['points'] = [dict(p['points'][0], x=x, y=y, pressure_value_gpa=pressure)
                   for x, y, pressure in [(200, 200, 100), (400, 400, 150), (600, 600, 200)]]
    readings, unresolved = calibrate_panel(p, Image.new('RGB', (200, 200), 'white'),
        {'file_id': 'main', 'sha256': 'a' * 64, 'page': 1}, [0, 0, 200, 200])
    assert not unresolved and len(readings) == 3
    assert [r['point']['pressure_value_gpa'] for r in readings] == [100, 150, 200]


def test_unreadable_point_keeps_its_identity_and_reason(tmp_path):
    from PIL import Image
    p = panel('line'); p['points'].pop(); p['unresolved'] = [{'category': 'YH10', 'series': 'green', 'reason': '柱被遮挡'}]
    readings, unresolved = calibrate_panel(p, Image.new('RGB', (200, 200)),
        {'file_id': 'main', 'sha256': 'a' * 64, 'page': 1}, [0, 0, 200, 200])
    assert len(readings) == 1 and unresolved[0]['reason'] == '柱被遮挡'


def test_source_hash_and_discovery_coverage_are_required(tmp_path):
    path, ir, source = original(tmp_path)
    with pytest.raises(ChartReadingError, match='身份'):
        enrich_document(ir, path, {**source, 'sha256': '0' * 64}, fake_model([]))
    with pytest.raises(ChartReadingError, match='页面'):
        enrich_document(ir, path, source, lambda *_args, **_kwargs: {'pages': []})
    assert len(ir.blocks) == 2


def test_formal_markdown_extraction_gets_graph_facts_before_workflow_scope(tmp_path, monkeypatch):
    from backend.ingest import upload_jobs
    path, ir, source = original(tmp_path); calls = []
    run = SimpleNamespace(profile='complementary', parser='fixture', version='1', status='completed', reading_state='read', error_code=None)
    monkeypatch.setattr(upload_jobs, 'parse_with_profile', lambda *_a, **_k: (ir, run))
    monkeypatch.setattr(upload_jobs, 'complete_json', fake_model(calls))
    monkeypatch.setattr(upload_jobs, 'get_state', lambda *_: {'status': 'extracting'})
    monkeypatch.setattr(upload_jobs, 'update_state', lambda *_a, **_k: None)
    monkeypatch.setattr(upload_jobs, 'artifact_directory', lambda *_: tmp_path / 'artifacts')
    text = upload_jobs._extract_markdown({'file_kind': 'pdf', 'parser_profile': 'complementary',
        'file_id': 'main', 'file_sha256': source['sha256'], 'task_id': 'a' * 32,
        'files': [{'file_id': 'main', 'role': 'main', 'original_filename': 'source.pdf'}]}, path)
    assert 'CALIBRATED ORIGINAL FIGURE READING' in text
    saved = DocumentIR.model_validate_json((tmp_path / 'artifacts/document_ir/main.json').read_text())
    assert saved.coverage['chart_reading']['readings'] == 2
    for block, expected in zip([b for b in saved.blocks if 'chart_reading' in b.metadata], [100, 150]):
        reading = block.metadata['chart_reading']
        assert reading['value_raw'] in text
        assert abs(reading['value_number'] - expected) <= reading['reading_precision']
    assert len(calls) == 2

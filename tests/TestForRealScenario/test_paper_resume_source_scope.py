"""同一原文加上图像派生事实后，论文阶段应沿用相同原文输入。"""
from copy import deepcopy
from pathlib import Path
import json

import pytest


def test_real_cah6_paper_input_identity_is_stable_after_chart_enrichment(monkeypatch):
    from backend.ingest import upload_source_bundle as bundle, upload_tasks
    from backend.ingest.scientific_context import fingerprint
    from backend.rag.llm_context import catalog_config
    root = Path(__file__).parent/'runs'/'20261109T181409Z-4e0a9338'
    if not (root/'paused-artifacts').exists():
        pytest.skip('此测试需要本机原始CaH6第4轮证据，通用边界另测')
    state = json.loads((root/'paused-task-state.json').read_text())
    checkpoint = json.loads((root/'paper-stage-checkpoint.json').read_text())
    model = catalog_config(state['execution_model']['catalog_id'])
    # 测试只用归档IR和原来源清单，不读/改业务任务状态或草稿。
    monkeypatch.setattr(upload_tasks, 'artifact_directory', lambda _: root/'paused-artifacts')
    sources = []
    for item in state['files']:
        ir = json.loads((root/'paused-artifacts'/'document_ir'/f"{item['file_id']}.json").read_text())
        sources.append({'file_id': item['file_id'], 'role': item['role'],
            'source_name': item['original_filename'], 'content': '派生内容已经进入Markdown：CALIBRATED ORIGINAL FIGURE READING'})
    monkeypatch.setattr(bundle, 'text_sources', lambda *_a, **_k: deepcopy(sources))
    original = bundle.paper_source_chunks(state['task_id'], state, root)
    identity = fingerprint({'sources': original, 'model': model.model, 'provider': model.provider,
        'endpoint': model.base_url, 'version': 2})
    assert identity == checkpoint['source_identity']
    assert not any('CALIBRATED ORIGINAL FIGURE READING' in c['content'] for c in original)
    assert not any('ORIGINAL FIGURE READING UNRESOLVED' in c['content'] for c in original)


def test_non_pdf_paper_sources_are_not_filtered(monkeypatch,tmp_path):
    from backend.ingest import upload_source_bundle as bundle, upload_tasks
    content = 'CALIBRATED ORIGINAL FIGURE READING is literal user text, not derived IR metadata.'
    monkeypatch.setattr(bundle,'text_sources',lambda *_: [{'file_id':'notes','role':'main','source_name':'notes.md','content':content}])
    monkeypatch.setattr(upload_tasks,'artifact_directory',lambda _:tmp_path)
    result=bundle.paper_source_chunks('task',{'files':[{'file_id':'notes','kind':'md'}]},tmp_path)
    assert result and content in ''.join(s['content'] for s in result)


def test_raw_ir_text_is_stable_across_derived_blocks_but_real_text_changes_invalidate(tmp_path, monkeypatch):
    from backend.ingest import upload_source_bundle as bundle, upload_tasks
    from backend.ingest.document_ir import DocumentIR, DocumentBlock, PageGeometry, content_hash
    root = tmp_path/'document_ir'; root.mkdir()
    raw = 'This literal CALIBRATED ORIGINAL FIGURE READING phrase belongs to the original paper.'
    ir = DocumentIR(document_id='d', source_file_id='main', source_sha256='a'*64, parse_profile='text',
        pages=[PageGeometry(pdf_page=1,width=600,height=800)], blocks=[DocumentBlock(block_id='original',
            block_type='paragraph',pdf_page=1,reading_order=0,text=raw,content_hash=content_hash(raw))])
    path=root/'main.json';path.write_text(ir.model_dump_json())
    state={'files':[{'file_id':'main','kind':'pdf','sha256':'a'*64}]}
    monkeypatch.setattr(upload_tasks,'artifact_directory',lambda _:tmp_path)
    monkeypatch.setattr(bundle,'text_sources',lambda *_: [{'file_id':'main','role':'main','source_name':'paper.pdf','content':'current markdown'}])
    before=bundle.paper_source_chunks('task',state,tmp_path)
    for i,key in enumerate(('chart_reading','chart_unresolved'),start=1):
        ir.blocks.append(DocumentBlock(block_id=f'derived-{i}',block_type='paragraph',pdf_page=1,
            reading_order=i,text='later generated fact',content_hash=content_hash('later generated fact'),metadata={key:{'version':1}}))
    path.write_text(ir.model_dump_json());snapshot=path.read_bytes()
    assert bundle.paper_source_chunks('task',state,tmp_path)==before
    assert path.read_bytes()==snapshot and raw in before[0]['content']
    ir.blocks[0].text += ' Actual parser text changed.'
    ir.blocks[0].content_hash=content_hash(ir.blocks[0].text);path.write_text(ir.model_dump_json())
    assert bundle.paper_source_chunks('task',state,tmp_path)!=before
    state['files'][0]['sha256']='b'*64
    with pytest.raises(ValueError,match='摘要不一致'):
        bundle.paper_source_chunks('task',state,tmp_path)

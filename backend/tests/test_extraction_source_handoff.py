"""互补原块必须能在失败续跑中交接，原OCR与科学门禁不改写。"""
from copy import deepcopy
import hashlib
import json
from types import SimpleNamespace

import pymupdf
import pytest

from backend.ingest.document_ir import DocumentIR, DocumentBlock, PageGeometry, content_hash


def case(tmp_path):
    path = tmp_path / 'source.pdf'
    with pymupdf.open() as pdf:
        page = pdf.new_page(width=200, height=200)
        page.insert_text((20, 30), 'LaH10 Tc = 200 K at 150 GPa')
        pdf.save(path)
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    def block(key, text, selected, parser):
        return DocumentBlock(block_id=key, block_type='paragraph', pdf_page=1, reading_order=0,
            text=text, bbox=(10, 10, 190, 50), content_hash=content_hash(text),
            metadata={'selected_for_reading': selected, 'source_kind': 'ocr' if selected else 'vision',
                      'source_parser': parser, 'source_parser_version': '1'})
    ir = DocumentIR(document_id='doc', source_file_id='main', source_sha256=sha,
        parse_profile='complementary', parser={'name':'complementary','version':'1','mode':'ocr'},
        pages=[PageGeometry(pdf_page=1,width=200,height=200)], blocks=[
            block('ocr','LaH1O Tc = 200 K at 150 GPa',True,'mineru'),
            block('repair','LaH10 Tc = 200 K at 150 GPa',False,'marker')],
        coverage={'routing':[{'anchor':'ocr','selected':'ocr','pdf_page':1,
            'alternatives':[{'block_id':'repair','engine':'marker'}]}]})
    context={'file_id':'main','source_sha256':sha,'pages':[{'geometry':{'pdf_page':1},
        'blocks':[ir.blocks[0].model_dump(mode='json')],'tables':[]}]}
    failed={'coverage_exclusions':[{'file_id':'main','block_id':'ocr','category':'unreadable','reason':'OCR identity ambiguous'}]}
    return path,ir,context,failed


def test_handoff_uses_actual_alternative_and_original_page_without_rewriting_ocr(tmp_path):
    from backend.ingest.extraction_sources import prepare_source_handoff
    path,ir,context,failed=case(tmp_path);before=deepcopy(ir.model_dump())
    handoff=prepare_source_handoff(context,failed,ir,path)
    blocks=handoff['context']['pages'][0]['blocks']
    assert [b['block_id'] for b in blocks]==['ocr','repair']
    assert blocks[0]['text']=='LaH1O Tc = 200 K at 150 GPa'
    assert blocks[1]['text']=='LaH10 Tc = 200 K at 150 GPa'
    assert len(handoff['images'])==1 and handoff['images'][0].startswith('data:image/png;base64,')
    assert handoff['audit']['source_sha256']==ir.source_sha256
    assert ir.model_dump()==before and context['pages'][0]['blocks'][0]['block_id']=='ocr'


@pytest.mark.parametrize('change',['foreign_file','foreign_page','unknown_alternative','source_hash'])
def test_handoff_does_not_borrow_foreign_or_unverified_source(tmp_path,change):
    from backend.ingest.extraction_sources import prepare_source_handoff
    path,ir,context,failed=case(tmp_path)
    if change=='foreign_file':failed['coverage_exclusions'][0]['file_id']='other'
    elif change=='foreign_page':ir.blocks[1].pdf_page=2
    elif change=='unknown_alternative':ir.coverage['routing'][0]['alternatives'][0]['block_id']='invented'
    elif change=='source_hash':path.write_bytes(path.read_bytes()+b'changed')
    if change=='source_hash':
        with pytest.raises(ValueError,match='身份'):prepare_source_handoff(context,failed,ir,path)
    else:assert prepare_source_handoff(context,failed,ir,path) is None


def test_full_read_chunk_recovers_only_failed_source_then_reuses_same_response(tmp_path,monkeypatch):
    from backend.ingest import upload_jobs as jobs
    from backend.rag import llm_context
    path,ir,context,failed=case(tmp_path)
    monkeypatch.setattr(jobs,'_chunk_result_path',lambda *_:tmp_path/'chunk.json')
    monkeypatch.setattr(jobs,'artifact_directory',lambda *_:tmp_path/'artifacts')
    d=tmp_path/'artifacts/document_ir';d.mkdir(parents=True)
    (d/'main.json').write_text(ir.model_dump_json())
    monkeypatch.setattr(llm_context,'get_llm_config',lambda:SimpleNamespace(provider='test',model='test',base_url='http://unused'))
    from backend.storage import paths
    monkeypatch.setattr(paths,'object_mode',lambda:False)
    calls=[]
    def model(_prompt,prompt,**options):
        calls.append(options)
        if len(calls)==1:return {'extraction_version':'1','material_states':[],**deepcopy(failed)}
        assert len(options['images'])==1 and 'repair' in prompt and 'LaH1O' in prompt
        evidence=[{'file_id':'main','pdf_page':1,'block_id':key,'quote_id':key,'quote':None} for key in ('ocr','repair')]
        return {'extraction_version':'1','material_states':[{'scope':'current_paper','material':'LaH10',
            'state_kind':'theoretical','structure_optimization':'unknown',
            'pressure_value_gpa':150,'evidences':deepcopy(evidence),
            'property_modules':[{'module_code':'superconductive_properties','records':[{
                'module_code':'superconductive_properties','record_type':'predicted_tc','property_code':'tc',
                'name_raw':'Tc','value_kind':'number','value_number':200,'value_raw':'200 K',
                'unit_raw':'K','canonical_unit':'K','method_code':'unknown',
                'payload':{'calculation_conditions':{},'parameters':{}},'evidences':evidence}]}]}]}
    monkeypatch.setattr(jobs,'complete_json',model)
    chunk=SimpleNamespace(chunk_index=0,content=json.dumps(context),section_name='Document IR',source_page=1)
    source={'file_id':'main','kind':'pdf','parser_profile':'complementary','stored_path':str(path),'sha256':ir.source_sha256}
    first=jobs._read_chunk('task',chunk,'main',source)
    assert first['coverage_exclusions'][0]['category']=='unreadable'
    repaired=jobs._read_chunk('task',chunk,'main',source)
    assert len(calls)==2 and not repaired['coverage_exclusions']
    assert repaired['_source_resolution']['targets']==['ocr']
    assert jobs._read_chunk('task',chunk,'main',source)==repaired and len(calls)==2
    from backend.ingest.document_claims import claims_from_candidates
    from backend.ingest.coverage_audit import audit_coverage
    claims=claims_from_candidates(repaired,{'main':ir})
    assert claims and all(c.status=='validated' for c in claims)
    report=audit_coverage(ir,claims,processed_pages=[1])
    assert report.status=='complete' and not report.requires_human
    invalid=deepcopy(claims)
    invalid[0].evidences[-1].quote='invented quote'
    assert audit_coverage(ir,invalid,processed_pages=[1]).requires_human
    assert (d/'main.json').read_text()==ir.model_dump_json()


@pytest.mark.parametrize('retired_reading', [False, True])
def test_phase_conflict_only_hands_back_original_sources_never_planner_answers(tmp_path,retired_reading):
    from backend.ingest.extraction_sources import inventory_scope_sources, prepare_source_handoff
    path,ir,context,_=case(tmp_path)
    extra=ir.blocks[1].model_copy(deep=True)
    extra.block_id='table-phase';extra.text='LaH10 at 150 GPa: Fm-3m.'
    extra.bbox=(10,80,190,110);extra.metadata['selected_for_reading']=True
    ir.blocks.append(extra)
    previous={'material_states':[{'material':'LaH10','pressure_value_gpa':150,
        'reported_space_group_symbol':'R-3m','property_modules':[{'records':[
            {'evidences':[{'file_id':'main','block_id':'ocr'}]}]}]}]}
    request={'sources':[{'source_id':'old','file_id':'main','block_id':'ocr','source_sha256':ir.source_sha256,
        'content':ir.blocks[0].text},{'source_id':'new','file_id':'main','block_id':'table-phase',
        'source_sha256':ir.source_sha256,'content':extra.text}],
        'candidates':[{'state_key':'initial','material':'LaH10','pressure_value_gpa':150,
            'reported_space_group_symbol':'R-3m','property_modules':[{'records':[
                {'evidences':[{'source_id':'old'}]}]}]}]}
    response={'states':[{'values':{'material':'LaH10','pressure_value_gpa':150,
        'reported_space_group_symbol':'Fm-3m'},'source_ids':['new']}],
        'assignments':[{'candidate_state_key':'initial','target_index':0,'source_ids':['new'],
                        'reason':'MODEL ANSWER MUST NOT BECOME SOURCE'}]}
    if retired_reading:
        ir.blocks[0].metadata.update(selected_for_reading=False,chart_reading={'version':'old'})
        current=ir.blocks[0].model_copy(deep=True)
        current.block_id='current-caption';current.block_type='caption';current.text='Actual original figure caption.'
        current.content_hash=content_hash(current.text);current.metadata={'selected_for_reading':True}
        ir.blocks.append(current)
        context['pages'][0]['blocks']=[current.model_dump(mode='json')]
    scope=inventory_scope_sources(context,previous,ir,request,response)
    assert scope['source_blocks']==['table-phase']
    assert scope['targets']==(['current-caption'] if retired_reading else ['ocr'])
    handoff=prepare_source_handoff(context,previous,ir,path,scope_sources=scope)
    assert any(b['block_id']=='table-phase' for p in handoff['context']['pages'] for b in p['blocks'])
    assert 'MODEL ANSWER' not in json.dumps(handoff)
    if retired_reading:assert 'LaH1O' not in json.dumps(handoff['context'])
    assert previous['material_states'][0]['reported_space_group_symbol']=='R-3m'
    saved={**previous,'_source_resolution':handoff['audit']}
    assert prepare_source_handoff(context,saved,ir,path)['audit']==handoff['audit']
    response['states'][0]['values']['reported_space_group_symbol']='R-3m'
    assert inventory_scope_sources(context,previous,ir,request,response) is None


def test_phase_scope_ignores_other_material_or_foreign_owned_record(tmp_path):
    from backend.ingest.extraction_sources import inventory_scope_sources
    _,ir,context,_=case(tmp_path)
    previous={'material_states':[{'material':'LaH10','pressure_value_gpa':150,
        'reported_space_group_symbol':'R-3m','property_modules':[{'records':[
            {'evidences':[{'file_id':'main','block_id':'ocr'}]}]}]}]}
    request={'sources':[],'candidates':[{'state_key':'other','material':'YH10','pressure_value_gpa':150,
        'reported_space_group_symbol':'R-3m','property_modules':[]}]}
    response={'states':[{'values':{'material':'YH10','pressure_value_gpa':150,
        'reported_space_group_symbol':'Fm-3m'},'source_ids':[]}],
        'assignments':[{'candidate_state_key':'other','target_index':0,'source_ids':[]}]}
    assert inventory_scope_sources(context,previous,ir,request,response) is None

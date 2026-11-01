"""真实建议生产者→叶子补空→快照/核对消费者；仅固定模型与外部存储边界。"""
from contextlib import contextmanager
from copy import deepcopy
from types import SimpleNamespace
import json

from backend.ingest import property_evidence as ev
from backend.ingest import scientific_evidence as science
from test_issue139_scientific_context import draft, context, candidate


import pytest


@pytest.mark.parametrize('generic_failure',[False,True])
def test_suggestion_pipeline_preserves_direct_facts_and_marks_inference(tmp_path,monkeypatch,generic_failure,db_session):
    d = draft()
    sources = context()['sources']
    stored = []
    def snapshot(task,owner,*,parsing_draft):
        rows = [r for r in ev.draft_records(parsing_draft,{}) if r['kind']=='property']
        return ev.complete_snapshot('upload',task,rows,sources,parsing_draft)
    monkeypatch.setattr(ev,'upload_snapshot',snapshot)
    monkeypatch.setattr('backend.ingest.upload_jobs._ensure_not_cancelled',lambda *_:None)
    monkeypatch.setattr('backend.ingest.upload_tasks.artifact_directory',lambda _:tmp_path)
    from sqlalchemy.orm import sessionmaker
    monkeypatch.setattr('backend.database.SessionLocal',sessionmaker(db_session.get_bind()))
    monkeypatch.setattr(science,'save_results',lambda s,snap,results,owner:stored.append((deepcopy(snap),deepcopy(results))))
    monkeypatch.setattr('backend.ingest.pdf_front_matter.correct_front_matter_results',lambda s,snap,results:results)
    failed_key = []
    def model(system,body,**kw):
        data=json.loads(body)
        if generic_failure and not failed_key:
            failed_key.append(data['records'][0]['key'])
        if generic_failure and [r['key'] for r in data['records']] == failed_key:
            raise TimeoutError('isolated unrelated field failure')
        results=[]
        for row in data['records']:
            if generic_failure and row['key'] in failed_key:
                continue
            result={'key':row['key'],'status':'supported','reason':'原文的同物相计算流程说明该设置的适用关系',
                    'source_ids':[data['sources'][0]['source_id']], 'basis_kind':'paper_inference'}
            if row.get('record_field')=='payload.calculation_conditions.k_grid':
                result.update(final_value='24×24×24',unique=True)
            results.append(result)
        return {'results':results}
    monkeypatch.setattr('backend.rag.llm.complete_json',model)
    results=ev.generate_upload_suggestions('task',d,1,scientific_sources=sources)
    r=d['material_states'][0]['property_modules'][0]['records'][0]
    assert r['value_min']==281 and r['value_max']==311
    assert r['payload']['parameters']['lambda_ep']==3.94
    assert r['payload']['calculation_conditions']['k_grid']=='24×24×24'
    snap,checks=stored[-1]
    field=next(row for row in snap['records'] if row.get('record_field')=='payload.calculation_conditions.k_grid')
    result=results[field['key']]
    assert result['status']=='supported' and result['adopted_basis']=='paper_inference'
    assert result['auto_corrected'] and not result['human_confirmed']
    checked=ev.checked_result(field,result,snap['chunks'])
    assert checked['status']=='supported' and checked['source_kind']=='paper_inference'
    r['payload']['calculation_conditions']['k_grid']='12×12×12'
    changed=next(row for row in snapshot('task',1,parsing_draft=d)['records'] if row.get('record_field')=='payload.calculation_conditions.k_grid')
    assert ev.checked_result(changed,result,sources)['status']!='supported'


def test_worker_finishes_direct_claim_gate_before_common_methods_fill(tmp_path,monkeypatch,db_session):
    import pymupdf
    from backend.ingest import upload_jobs as jobs
    from backend.ingest.scientific_context import READ_PROMPT,scientific_fingerprint
    from backend.ingest.domain_extraction import DOMAIN_SYSTEM_PROMPT
    text='LaH10 has a critical temperature of 200 K at 150 GPa. Phonons use a 24x24x24 k grid for all pressures.'
    path=tmp_path/'paper.pdf'
    with pymupdf.open() as pdf:
        page=pdf.new_page();page.insert_textbox(pymupdf.Rect(40,40,550,200),text,fontsize=12);pdf.save(path)
    task='a'*32
    artifacts=tmp_path/'artifacts';artifacts.mkdir()
    markdown=tmp_path/'markdown'/f'{task}.md';markdown.parent.mkdir()
    state={'task_id':task,'status':'queued','stage':'queued','file_path':str(path),'filename':'paper.pdf',
           'file_kind':'pdf','file_sha256':jobs.sha256_file(path),'parser_profile':'text','user_id':1}
    def update(_,**changes):state.update(changes);return dict(state)
    monkeypatch.setattr(jobs,'get_state',lambda _:dict(state))
    monkeypatch.setattr(jobs,'update_state',update)
    for name in ('_find_existing_by_hash','_find_existing_paper','_schedule_terminal_cleanup','_start_automatic_evidence_check'):
        monkeypatch.setattr(jobs,name,lambda *a:None)
    monkeypatch.setattr(jobs,'markdown_path',lambda _:markdown)
    monkeypatch.setattr(jobs,'artifact_directory',lambda _:artifacts)
    monkeypatch.setattr(jobs,'artifact_path',lambda _:artifacts/'result.json')
    monkeypatch.setattr(jobs,'data_path',lambda _:markdown.parent)
    monkeypatch.setattr(jobs,'extract_references_from_pdf',lambda _:{'status':'unavailable','references':[]})
    monkeypatch.setattr(jobs,'extract_structure_candidates',lambda *a,**kw:[])
    # 当前共享工作区可能正在实施 #135；其角色审阅不属于本测试的科学链路。
    import importlib.util
    if importlib.util.find_spec('backend.ingest.document_roles'):
        monkeypatch.setattr('backend.ingest.document_roles.assess_roles',lambda files,texts:{
            'status':'resolved','source_hash':'fixture','files':[{'file_id':f['file_id'],'effective_role':f['role']} for f in files]})
    monkeypatch.setattr('backend.ingest.upload_tasks.artifact_directory',lambda _:artifacts)
    def snapshot(task,owner,*,parsing_draft):
        rows=[r for r in ev.draft_records(parsing_draft,{}) if r['kind']=='property']
        return ev.complete_snapshot('upload',task,rows,ev.source_chunks(markdown.read_text(),'main'),parsing_draft)
    monkeypatch.setattr(ev,'upload_snapshot',snapshot)
    monkeypatch.setattr(ev,'evaluate_batch',lambda rows,*a,**kw:[{'status':'supported','reason':'原文报告该结果',
        'evidences':[{'file_id':'main','quote':'200 K'}],'location_errors':[]} for _ in rows])
    from sqlalchemy.orm import sessionmaker
    monkeypatch.setattr('backend.database.SessionLocal',sessionmaker(db_session.get_bind()))
    monkeypatch.setattr(science,'save_results',lambda *a:None)
    monkeypatch.setattr('backend.ingest.pdf_front_matter.correct_front_matter_results',lambda s,snap,results:results)
    saved=[]
    monkeypatch.setattr(jobs,'save_draft',lambda _,value:saved.append(deepcopy(value)))
    def direct(system,prompt,**kw):
        from backend.ingest.scientific_form_filling import PROMPT as FILL_PROMPT
        if system == FILL_PROMPT:
            request = json.loads(prompt)
            row = request['candidates'][0]
            source = next(s for s in request['sources'] if '200 K' in s['content'])
            return {'done': True, 'records': [{'candidate_ids': [row['candidate_id']],
                'group': 'same-conditions', 'method': 'unknown',
                'values': {'value_kind': 'number', 'value_number': 200, 'method_code': 'unknown'},
                'source_ids': [source['source_id']], 'reason': '保留原文数值，方法未报告'}],
                'excluded': [], 'unresolved': []}
        if system==DOMAIN_SYSTEM_PROMPT:
            context=json.loads(prompt[prompt.index('{'):])
            b=context['pages'][0]['blocks'][0]
            e={'file_id':'main','pdf_page':1,'block_id':b['block_id'],'quote':b['text']}
            return {'extraction_version':'1','metadata':{'title':'Paper'},'material_states':[{
                'scope':'current_paper','material':'LaH10','state_kind':'theoretical','pressure_value_gpa':150,
                'evidences':[e],'property_modules':[{'module_code':'superconductive_properties','records':[{
                    'module_code':'superconductive_properties','record_type':'predicted_tc','property_code':'tc',
                    'name_raw':'critical temperature','value_kind':'number','value_number':200,'value_raw':'200',
                    'canonical_unit':'K','method_code':'unknown','payload':{'calculation_conditions':{}},'evidences':[e]}]}]}]}
        return {'paper':{'title':'Paper','paper_type':'theoretical','year':2026},'material_states':[]}
    monkeypatch.setattr(jobs,'complete_json',direct)
    def methods(system,body,**kw):
        # 这是实际 Worker 到实际建议生产者的时序断言，不 Mock Claim/覆盖路径。
        claims=json.loads((artifacts/'final_claims.json').read_text())
        assert claims and all(c['status']=='validated' for c in claims)
        assert all(c['basis_kind']=='paper_quote' for c in claims)
        data=json.loads(body)
        results=[]
        for row in data['records']:
            result={'key':row['key'],'status':'supported','reason':'原文明确该压力的结果及共用声子网格',
                    'source_ids':[data['sources'][0]['source_id']], 'basis_kind':'paper_inference'}
            if row.get('record_field')=='payload.calculation_conditions.k_grid':
                result.update(final_value='24x24x24',unique=True)
            results.append(result)
        return {'results':results}
    monkeypatch.setattr('backend.rag.llm.complete_json',methods)
    assert jobs._process_upload_task(task)['status']=='ready'
    assert saved[0]['form_filling_report']['status'] == 'completed'
    r=saved[0]['material_states'][0]['property_modules'][0]['records'][0]
    assert r['payload']['tc_group']['version'] == 1
    assert r['payload']['calculation_conditions']['k_grid']=='24x24x24'
    assert state['suggestions_status']=='completed'
    assert state['preview_phase']=='saving'


def test_structured_table_contract_retry_is_bounded_and_keeps_raw_attempts(tmp_path,monkeypatch):
    from backend.ingest import upload_jobs as jobs
    from backend.ingest.chunker import Chunk
    from backend.ingest.document_parsers import ParserError
    monkeypatch.setenv('FILE_STORAGE_BACKEND','local')
    monkeypatch.setattr(jobs,'_chunk_result_path',lambda *a,**kw:tmp_path/'result.json')
    monkeypatch.setattr(jobs,'_ensure_not_cancelled',lambda *_:None)
    source={'file_id':'f','pages':[{'geometry':{'pdf_page':1},'blocks':[{'pdf_page':1,'block_id':'b','text':'Table 1 original note'}],
        'tables':[{'table_id':'t','row_count':2}]}]}
    chunk=Chunk(0,0,'Table',None,json.dumps(source),100)
    invalid={'extraction_version':'1','material_states':[],'coverage_exclusions':[{
        'file_id':'f','table_id':'t','row_index':-1,'category':'out_of_model_scope','reason':'lattice coordinates'}]}
    calls=[]
    def model(system,prompt,**kw):
        calls.append(prompt)
        if len(calls)==1:return deepcopy(invalid)
        assert 'row_index' in prompt and 'Table 1 original note' in prompt
        return {'extraction_version':'1','material_states':[],'coverage_exclusions':[]}
    monkeypatch.setattr(jobs,'complete_json',model)
    jobs._read_chunk('task',chunk,'f',{'kind':'pdf','parser_profile':'complementary'})
    assert len(calls)==2
    raw=list(tmp_path.rglob('raw.json'))
    assert len(raw)==2 and any(json.loads(p.read_text()).get('coverage_exclusions') for p in raw)
    (tmp_path/'result.json').unlink()
    monkeypatch.setattr(jobs,'complete_json',lambda *a,**kw:deepcopy(invalid))
    import pytest
    with pytest.raises(ParserError,match='不符合契约'):
        jobs._read_chunk('task',chunk,'f',{'kind':'pdf','parser_profile':'complementary'})


def test_only_hash_verified_margin_download_stamp_is_non_scientific(tmp_path):
    import pymupdf
    from backend.ingest.structured_pdf import IrBuilder
    from backend.ingest.document_ir import PageGeometry
    from backend.ingest.document_parsers import DocumentSource,ParseOptions
    from backend.ingest.coverage_audit import verified_download_stamps,audit_coverage
    path=tmp_path/'source.pdf'
    with pymupdf.open() as pdf:
        page=pdf.new_page()
        page.insert_text((12,700),'Downloaded from https://publisher.invalid/article on October 15',rotate=90,fontsize=8)
        page.insert_text((120,150),'Tc is unknown: damaged scientific text',fontsize=10)
        pdf.save(path)
    with pymupdf.open(path) as pdf:
        boxes=pdf[0].get_text('blocks')
        margin=next(b for b in boxes if 'Downloaded' in b[4])
        body=next(b for b in boxes if 'Tc is unknown' in b[4])
        geometry=PageGeometry(pdf_page=1,width=pdf[0].rect.width,height=pdf[0].rect.height)
    builder=IrBuilder(DocumentSource(path,'f'),ParseOptions(profile='mineru'),'mineru','test',[geometry],'ocr')
    stamp=builder.add(1,'paragraph','0 ) 0 q /: o 4',margin[:4])
    scientific=builder.add(1,'paragraph','Tc ??? unreadable',body[:4])
    ir=builder.finish()
    verified=verified_download_stamps(ir,path,[])
    assert [x['block_id'] for x in verified]==[stamp.block_id]
    assert verified[0]['verification']['source_sha256']==ir.source_sha256
    exclusions=[*verified,{'file_id':'f','block_id':scientific.block_id,'category':'unreadable','reason':'scientific text remains unreadable'}]
    report=audit_coverage(ir,[],processed_pages=[1],exclusions=exclusions)
    assert report.requires_human and 'unreadable_exclusion_present' in report.limitations
    assert report.exclusions[0]['verification']['rule']=='download-stamp-v1'
    ir.source_sha256='0'*64
    assert verified_download_stamps(ir,path,[])==[]

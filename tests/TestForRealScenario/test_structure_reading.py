"""#49/#204：真实PDF进入内容识别，不因表头拼写静默丢失结构。"""
from pathlib import Path
import hashlib
import pytest


def test_pdf_positions_table_reaches_content_reader_before_legacy_filter(tmp_path, monkeypatch):
    import pymupdf
    from backend.ingest import upload_jobs
    from backend.rag import llm
    pdf=tmp_path/"positions.pdf"
    with pymupdf.open() as doc:
        page=doc.new_page();page.insert_text((40,40),"Lattice parameters and atomic positions\nNaCl 10 GPa\na = b = c = 5.64\nalpha = beta = gamma = 90\nNa 0.000 0.000 0.000\nCl 0.500 0.500 0.500")
        doc.save(pdf)
    called=[]
    class Observed(Exception): pass
    def read(*args, **kwargs):
        called.append(kwargs);raise Observed()
    monkeypatch.setattr(llm,"complete_json",read)
    monkeypatch.setattr(upload_jobs,"_ensure_not_cancelled",lambda _:{"status":"extracting"})
    monkeypatch.setattr(upload_jobs,"artifact_directory",lambda _:tmp_path/"artifacts")
    try:
        upload_jobs._extract_pdf_structure_candidates('live',"Lattice parameters and atomic positions",pdf,
            {"file_id":"actual-pdf","role":"supplementary","original_filename":"positions.pdf","sha256":hashlib.sha256(pdf.read_bytes()).hexdigest()})
    except Observed:
        pass
    assert called, "实际PDF被旧关键词筛选直接忽略，AI没有机会识别结构内容"
    assert (tmp_path/'artifacts/structure_reading/actual-pdf/call-0-started.json').is_file()
    assert (tmp_path/'artifacts/structure_reading/actual-pdf/call-0-failed.json').is_file()


def reported():
    return {'material':'NaCl','pressure_value_gpa':10,'space_group_symbol':'Pm-3m',
        'coordinate_mode':'fractional','length_unit':'angstrom','angle_unit':'degree','position_unit':'dimensionless',
        'cell_parameters':dict(a=5.64,b=5.64,c=5.64,alpha=90,beta=90,gamma=90),
        'cell_source_ids':['cell','angle'],
        'atoms':[{'element':'Na','coordinates':[0,0,0],'source_id':'na'},
                 {'element':'Cl','coordinates':[.5,.5,.5],'source_id':'cl'}],
        'source_ids':['header'],'uncertainties':[],'reason':'原表明确晶格、分数坐标及条件。'}


def catalog():
    texts={'cell':'a = b = c = 5.64 Angstrom','angle':'alpha = beta = gamma = 90 degree',
           'header':'NaCl at 10 GPa, Pm-3m, fractional atomic positions',
           'na':'Na 0.000 0.000 0.000','cl':'Cl 0.500 0.500 0.500'}
    return {key:{'source_id':key,'file_id':'actual-pdf','pdf_page':1,'block_id':key,
                 'bbox':[0,0,10,10],'content':value} for key,value in texts.items()}


def source():
    return {'file_id':'actual-pdf','role':'supplementary','filename':'source.pdf','sha256':'a'*64}


def test_complete_source_geometry_exports_and_retains_original_coordinate_rows():
    from backend.ingest.structure_reading import _candidates
    from backend.services.structure_candidates import read_atoms
    c=_candidates({'structures':[reported()]},catalog(),{1},source())[0]
    assert c['status']=='valid' and c['confirmation']=='unreviewed'
    assert {s['block_id'] for s in c['sources']}==set(catalog())
    assert c['reported_structure']['atomic_positions']==reported()['atoms']
    assert len(read_atoms('cif',c['representations']['conventional']['cif']['text']))==2


@pytest.mark.parametrize('fault',['wrong_atom_row','invented_number','unknown_mode','wrong_unit','not_imaged','wrong_formula','phase_conflict'])
def test_unsafe_geometry_keeps_specific_issue_without_erasing_valid_neighbor(fault):
    from copy import deepcopy
    from backend.ingest.structure_reading import _candidates
    item=reported();pages={1}
    if fault=='wrong_atom_row':item['atoms'][0]['source_id']='cl'
    elif fault=='invented_number':item['atoms'][1]['coordinates'][0]=.6
    elif fault=='unknown_mode':item['coordinate_mode']='unknown'
    elif fault=='wrong_unit':item['length_unit']='unknown'
    elif fault=='not_imaged':pages=set()
    elif fault=='wrong_formula':item['material']='NaCl2'
    else:item['space_group_symbol']='Fm-3m'
    c=_candidates({'structures':[item]},catalog(),pages,source())[0]
    assert c['status']=='blocked' and c['validation']['message']
    assert not c['representations'] and c['confirmation']=='unreviewed'
    # 同一响应中的其他完整结构继续存在，不删除原失败项或补造数值。
    neighbors=_candidates({'structures':[deepcopy(item),reported()]},catalog(),{1},source())
    if fault!='not_imaged':assert [c['status'] for c in neighbors]==['blocked','valid']


def test_native_image_result_is_delivered_with_matching_tool_id_before_final_geometry(tmp_path):
    import json
    import pymupdf
    from backend.ingest.structure_reading import extract_structure_candidates
    pdf=tmp_path/'source.pdf'
    with pymupdf.open() as doc:
        page=doc.new_page();page.insert_text((40,40),'NaCl at 10 GPa, Pm-3m, fractional atomic positions\na = b = c = 5.64 Angstrom\nalpha = beta = gamma = 90 degree\nNa 0.000 0.000 0.000\nCl 0.500 0.500 0.500');doc.save(pdf)
    src={**source(),'sha256':hashlib.sha256(pdf.read_bytes()).hexdigest()};calls=[];events=[]
    def model(system,payload,**options):
        request=json.loads(payload);calls.append(options)
        if len(calls)==1:
            return {'action':{'name':'read_original_page','arguments':{'file_id':'actual-pdf','page':1}},
                    '_tool_call':{'id':'actual-native-call','type':'function','function':{'name':'read_original_page','arguments':'{"file_id":"actual-pdf","page":1}'}}}
        assert len(options['images'])==1 and options['images'][0].startswith('data:image/png;base64,')
        assert options['tool_history'][0]['tool_calls'][0]['id']==options['tool_history'][1]['tool_call_id']=='actual-native-call'
        rows=request['sources'];ids={name:next(r['source_id'] for r in rows if r['content'].startswith(prefix))
            for name,prefix in [('header','NaCl at'),('cell','a ='),('angle','alpha ='),('na','Na '),('cl','Cl ')]}
        item=reported();item['source_ids']=[ids['header']];item['cell_source_ids']=[ids['cell'],ids['angle']]
        for atom,key in zip(item['atoms'],['na','cl']):atom['source_id']=ids[key]
        return {'action':{'name':'report_structures','arguments':{'structures':[item],'uncertainties':[],'reason':'已核对本页完整原表'}}}
    result=extract_structure_candidates('',source=src,pdf_path=pdf,model=model,on_event=events.append)
    assert result[0]['status']=='valid' and len(calls)==2
    receipt=next(e for e in events if e['status']=='completed' and e['images_received'])
    assert receipt['image_pages']==[1] and receipt['tool_history'][1]['tool_call_id']=='actual-native-call'


def test_transport_failure_preserves_partial_response_without_exception_credentials(tmp_path):
    import json
    import pymupdf
    from backend.ingest.structure_reading import extract_structure_candidates
    pdf=tmp_path/'source.pdf'
    with pymupdf.open() as doc:
        doc.new_page().insert_text((40,40),'Lattice and atomic positions');doc.save(pdf)
    events=[]
    def model(*args,**kwargs):
        kwargs['on_partial']('{"structures":[')
        raise RuntimeError('credential-sentinel-must-not-be-logged')
    with pytest.raises(RuntimeError):extract_structure_candidates('',source={**source(),'sha256':hashlib.sha256(pdf.read_bytes()).hexdigest()},pdf_path=pdf,model=model,on_event=events.append)
    assert events[-1]['status']=='failed' and events[-1]['partial_response']=='{"structures":['
    assert 'credential-sentinel' not in json.dumps(events)


def test_file_uncertainty_keeps_valid_geometry_and_visible_failure_instead_of_raising():
    from backend.ingest.structure_reading import _reading_result
    result=_reading_result({'structures':[reported()],'uncertainties':['另一页坐标基底尚未确定'],'reason':'已读取原表'},catalog(),catalog(),{1},source())
    assert [c['status'] for c in result]==['valid','blocked']
    assert '另一页坐标基底尚未确定' in result[1]['validation']['message']
    assert result[1]['sources'][0]['quote']==''  # 模型判断不能冒充作者引句。


def test_structure_assignment_unpacks_actual_ir_blocks_without_collapsing_equal_cells():
    from backend.ingest.document_ir import DocumentIR,DocumentBlock,PageGeometry,content_hash
    from backend.ingest.domain_extraction import structured_chunks
    from backend.ingest.canonical_structure import _source_rows
    ir=DocumentIR(document_id='si',source_file_id='si',source_sha256='a'*64,parse_profile='test',
        pages=[PageGeometry(pdf_page=1,width=100,height=100)],
        blocks=[DocumentBlock(block_id=k,block_type='table_cell',pdf_page=1,reading_order=i,text='300',content_hash=content_hash('300')) for i,k in enumerate(['row-a','row-b'])])
    sources=[{'file_id':'si','file_role':'supplementary','content':c.content} for c in structured_chunks(ir)]
    rows=_source_rows([],sources)
    assert len(rows)==2 and {r['block_id'] for r in rows}=={'row-a','row-b'}
    assert all(r['content']=='300' for r in rows)


def test_ai_discovery_does_not_remove_existing_explicit_geometry_decoder(tmp_path):
    import pymupdf
    from backend.ingest.structure_reading import extract_structure_candidates
    text='Atomic coordinates (fractional)\na = 5.64 b = 5.64 c = 5.64\nalpha = 90 beta = 90 gamma = 90\nNa 0.000 0.000 0.000\nCl 0.500 0.500 0.500'
    pdf=tmp_path/'explicit.pdf'
    with pymupdf.open() as doc:
        doc.new_page().insert_text((40,40),text);doc.save(pdf)
    calls=[]
    def model(*args,**kwargs):
        calls.append(True)
        return {'action':{'name':'report_structures','arguments':{'structures':[],'uncertainties':[],'reason':'读取完成'}}}
    result=extract_structure_candidates(text,pdf_path=pdf,source={**source(),'sha256':hashlib.sha256(pdf.read_bytes()).hexdigest()},model=model)
    assert calls and any(c['status']=='valid' for c in result)


def test_upload_structure_callback_checks_cancellation_without_using_state_truthiness(monkeypatch):
    from backend.ingest import upload_jobs
    monkeypatch.setattr(upload_jobs, '_ensure_not_cancelled', lambda _: {'status':'extracting','task_id':'live'})
    assert upload_jobs._structure_reading_cancelled('live') is False
    def cancelled(_): raise upload_jobs.UploadCancelled()
    monkeypatch.setattr(upload_jobs, '_ensure_not_cancelled', cancelled)
    with pytest.raises(upload_jobs.UploadCancelled): upload_jobs._structure_reading_cancelled('live')


def _tool_action(name, page, index):
    import json
    arguments={'file_id':'actual-pdf',**({'page':page}if page is not None else {})}
    return {'action':{'name':name,'arguments':arguments},'_tool_call':{'id':f'original-read-{index}',
        'type':'function','function':{'name':name,'arguments':json.dumps(arguments)}}}


def test_original_page_is_one_action_and_prior_native_receipts_and_image_identity_survive(tmp_path):
    import json
    import pymupdf
    from backend.ingest.structure_reading import extract_structure_candidates
    pdf=tmp_path/'three-pages.pdf'
    with pymupdf.open() as doc:
        for page in range(1,4):doc.new_page().insert_text((40,40),f'Page {page}: actual source row')
        doc.save(pdf)
    actions=[('read_original_page',3),('read_document',None),('read_original_page',1)]
    count=0
    def model(system,payload,**options):
        nonlocal count
        request=json.loads(payload);index=count;count+=1
        assert request['remaining_actions']==12-index,'每个原生只读请求只能计费一次'
        if index:
            history=options['tool_history'];assert len(history)==2*index,'先前成功读取的原生回执不得丢失'
            for i in range(index):assert history[2*i]['tool_calls'][0]['id']==history[2*i+1]['tool_call_id']==f'original-read-{i}'
            pages=[3]if index<3 else [3,1]
            assert [r['pdf_page']for r in request['attached_page_images']]==pages
            assert [r['image_index']for r in request['attached_page_images']]==list(range(1,len(pages)+1))
            assert all(r['file_id']=='actual-pdf'and r['source_sha256']==hashlib.sha256(pdf.read_bytes()).hexdigest()for r in request['attached_page_images'])
            assert len(options['images'])==len(pages)
        if index<len(actions):return _tool_action(*actions[index],index)
        return {'action':{'name':'report_structures','arguments':{'structures':[],'uncertainties':['本用例只验证读取协议，未判断有无结构'],'reason':'保留未完成结构判断'}}}
    result=extract_structure_candidates('',source={**source(),'sha256':hashlib.sha256(pdf.read_bytes()).hexdigest()},pdf_path=pdf,model=model)
    assert count==4 and result and all(r['status']=='blocked'for r in result)


def test_real_seventh_native_read_sequence_fits_existing_budget_without_faking_geometry(tmp_path):
    import json
    import pymupdf
    from backend.ingest.structure_reading import extract_structure_candidates
    pdf=tmp_path/'eight-pages.pdf'
    with pymupdf.open() as doc:
        for page in range(1,9):doc.new_page().insert_text((40,40),f'Page {page} original source')
        doc.save(pdf)
    # 真实第七轮的八次原生请求；不将旧模型几何答案冒充新的提取。
    actions=[('read_document',None),('read_original_page',6),('read_original_page',7),('read_original_page',8),
             ('read_document',None),('read_original_page',6),('read_document',None),('read_original_page',6)]
    calls=0
    def model(system,payload,**options):
        nonlocal calls
        index=calls;calls+=1
        if index<len(actions):return _tool_action(*actions[index],index)
        assert json.loads(payload)['remaining_actions']==4
        return {'action':{'name':'report_structures','arguments':{'structures':[],'uncertainties':['固定失败序列重放，未提供科学几何结论'],'reason':'仅验证真实读取序列不会被双计费拦截'}}}
    result=extract_structure_candidates('',source={**source(),'sha256':hashlib.sha256(pdf.read_bytes()).hexdigest()},pdf_path=pdf,model=model)
    assert calls==9 and all(r['status']=='blocked'for r in result)


def test_native_read_budget_still_stops_at_twelve_actions(tmp_path):
    import pymupdf
    from backend.ingest.document_agent import AgentStopped
    from backend.ingest.structure_reading import extract_structure_candidates
    pdf=tmp_path/'bounded.pdf'
    with pymupdf.open()as doc:
        doc.new_page().insert_text((40,40),'Original page');doc.save(pdf)
    calls=0
    def model(*args,**options):
        nonlocal calls
        index=calls;calls+=1
        return _tool_action('read_original_page',1,index)
    with pytest.raises(AgentStopped,match='agent_budget_exhausted'):
        extract_structure_candidates('',source={**source(),'sha256':hashlib.sha256(pdf.read_bytes()).hexdigest()},pdf_path=pdf,model=model)
    assert calls==13,'12次合法行动后，第13次被拒绝，未扩大预算或吞掉失败'


def test_scope_excluded_structure_is_archived_without_blocking_allowed_neighbor(tmp_path):
    import json,pymupdf
    from backend.ingest.structure_reading import extract_structure_candidates
    pdf=tmp_path/"scope.pdf"
    with pymupdf.open() as doc:
        page=doc.new_page();page.insert_text((40,40),
            "NaCl at 10 GPa, Pm-3m, fractional atomic positions\na = b = c = 5.64 Angstrom\nalpha = beta = gamma = 90 degree\nNa 0 0 0\nCl 0.5 0.5 0.5\nKCl at 10 GPa, Pm-3m, fractional atomic positions\na = b = c = 6.28 Angstrom\nalpha = beta = gamma = 90 degree\nK 0 0 0\nCl 0.5 0.5 0.5")
        doc.save(pdf)
    src={**source(),"sha256":hashlib.sha256(pdf.read_bytes()).hexdigest()}
    scope={"excluded_materials":[{"material":"KCl","reason":"本文只报告数值Tc范围","evidences":[{"file_id":"main","content":"KCl Tc below 56 K."}]}]}
    calls=[];events=[]
    def model(prompt,payload,**options):
        request=json.loads(payload);calls.append(request)
        if len(calls)==1:
            return {"action":{"name":"read_original_page","arguments":{"file_id":src["file_id"],"page":1}}}
        rows=request["sources"]
        def ref(prefix,last=False):
            found=[r["source_id"]for r in rows if r["content"].startswith(prefix)]
            return found[-1]if last else found[0]
        good=reported();good.update(source_ids=[ref("NaCl at")],cell_source_ids=[ref("a = b = c = 5.64"),ref("alpha")])
        good["atoms"][0]["source_id"]=ref("Na ")
        good["atoms"][1]["source_id"]=ref("Cl ")
        bad=reported();bad.update(material="KCl",source_ids=[ref("KCl at")],cell_source_ids=[ref("a = b = c = 6.28"),ref("alpha",True)])
        bad["cell_parameters"].update(a=6.28,b=6.28,c=6.28)
        bad["atoms"][0].update(element="K",source_id=ref("K "))
        bad["atoms"][1]["source_id"]=ref("Cl ",True)
        return {"structures":[good,bad],"uncertainties":[],"reason":"原表两个完整结构；范围决定另行由既有元数据拥有。"}
    result=extract_structure_candidates("",source=src,pdf_path=pdf,model=model,on_event=events.append,material_scope=scope)
    valid=[c for c in result if c["status"]=="valid"]
    assert len(valid)==1 and valid[0]["reported_structure"]["material"]=="NaCl"
    excluded=[e for e in events if e["status"]=="scope-excluded"]
    assert len(excluded)==1
    trace=excluded[0]["exclusions"][0]
    assert trace["structure"]["material"]=="KCl" and trace["sources"]
    assert trace["scope_decision"]==scope["excluded_materials"][0]
    assert len(calls)==2

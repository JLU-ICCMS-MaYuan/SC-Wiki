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

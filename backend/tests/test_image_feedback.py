from copy import deepcopy
import json
import pytest

from backend.tests.test_chart_reading import original, panel
from backend.ingest.chart_reading import enrich_document
from backend.ingest.image_feedback import FeedbackProgress,issue_signature


def test_progress_requires_new_evidence_and_survives_restore():
    progress = FeedbackProgress()
    assert progress.observe('crop', {'region':'a'}, {'sha':'one'})
    assert not progress.observe('crop', {'region':'a'}, {'sha':'one'})
    restored = FeedbackProgress(json.loads(json.dumps(progress.state())))
    assert not restored.observe('crop', {'region':'a'}, {'sha':'one'})
    assert restored.observe('crop', {'region':'a'}, {'sha':'two'})


def test_reworded_real_missing_prh9_is_not_new_evidence():
    before=[{'category':'PrH₉','series':'μ* = 0.1','reason':'No visible green bar; not zero.'}]
    after=[{'category':'PrH9','series':'μ*=0.1','reason':'No distinguishable bar above baseline after inspecting crop.'}]
    assert issue_signature(before)==issue_signature(after)
    progress=FeedbackProgress()
    assert progress.observe('program_verification','original-tc-panel',issue_signature(before))
    assert not progress.observe('program_verification','original-tc-panel',issue_signature(after))


def test_program_failure_returns_to_same_model_and_executes_real_crop(tmp_path):
    path, ir, source = original(tmp_path)
    calls = []
    def model(prompt, content, **opts):
        data=json.loads(content);calls.append((data,opts))
        if 'image_pages' in data:
            return {'pages':[{'page':1,'figures':[{'bbox':[100,100,900,900],
                'label':'Fig. 1','target':True,'reason':'Tc bars'}]}]}
        reading=panel()
        if len(calls)==2:
            reading['points'][0]['x']=5
            return {'panels':[reading],'notes':[]}
        if len(calls)==3:
            assert data['verification_issues'][0]['point']['category']=='YH10'
            box=list(data['crop_bbox']);box[0]+=1
            return {'action':{'name':'adjust_image_region','arguments':{
                'region_id':data['region_id'],'bbox_page':box,
                'reason':'重新确认YH10两条系列柱内部位置','dpi':600}}}
        assert data['observation']['action']=='adjust_image_region'
        assert opts['images'][1].startswith('data:image/png;base64,')
        import base64,hashlib
        assert hashlib.sha256(base64.b64decode(opts['images'][1].split(',',1)[1])).hexdigest()==data['crop_sha256']
        return {'panels':[reading],'notes':[]}
    report=enrich_document(ir,path,source,model)
    assert report['readings']==2 and len(calls)==4
    assert any('verification_issues' in call[0] for call in calls)


def test_pixel_coordinates_outside_normalized_domain_are_returned_for_repair(tmp_path):
    path, ir, source = original(tmp_path)
    requests=[]
    def model(prompt,content,**options):
        data=json.loads(content);requests.append(data)
        if 'image_pages' in data:
            return {'pages':[{'page':1,'figures':[{'bbox':[100,100,900,900],
                'label':'Fig. 1','target':True,'reason':'Tc bars'}]}]}
        reading=panel()
        if len(requests)==2:reading['points'][0]['x']=1453
        else:
            assert data['verification_issues'][0]['reason_code']=='INVALID_PANEL_OBSERVATION'
        return {'panels':[reading],'notes':[]}
    report=enrich_document(ir,path,source,model)
    assert report['readings']==2 and len(requests)==3


def test_discovery_hints_and_output_share_normalized_page_coordinates(tmp_path):
    path,ir,source=original(tmp_path)
    def model(prompt,content,**options):
        request=json.loads(content)
        if 'image_pages' in request:
            for hint in request['regions']:
                assert hint['coordinate_space']=='page_normalized_0_1000'
                if hint['block_id'] is None:continue
                original_block=ir.block(hint['block_id'])
                geometry=ir.pages[0]
                assert hint['bbox']==[original_block.bbox[0]*1000/geometry.width,
                    original_block.bbox[1]*1000/geometry.height,original_block.bbox[2]*1000/geometry.width,
                    original_block.bbox[3]*1000/geometry.height]
            return {'pages':[{'page':1,'figures':[{'bbox':[100,100,900,900],
                'label':'Fig. 1','target':True,'reason':'Tc bars'}]}]}
        return {'panels':[panel()],'notes':[]}
    assert enrich_document(ir,path,source,model)['readings']==2


def test_repeated_unreadable_panel_is_not_saved_as_a_value(tmp_path):
    path, ir, source=original(tmp_path)
    def model(prompt,content,**options):
        if 'image_pages' in json.loads(content):
            return {'pages':[{'page':1,'figures':[{'bbox':[100,100,900,900],
                'label':'Fig. 1','target':True,'reason':'Tc bars'}]}]}
        reading=panel();reading['points'][0]['x']=1453
        return {'panels':[reading],'notes':[]}
    report=enrich_document(ir,path,source,model)
    assert not report['readings'] and report['unresolved']


def test_feedback_checkpoint_resumes_with_pixels_and_without_reasking_successes(tmp_path,monkeypatch):
    import httpx
    import pytest
    from types import SimpleNamespace
    from openai import APIStatusError
    from backend.rag import llm
    from backend.tests.test_model_runtime import setup_runtime
    from backend.ingest.model_runtime import ExecutionStopped
    path,ir,source=original(tmp_path)
    requests=[];available=[False]
    def complete(prompt,content,**options):
        data=json.loads(content);requests.append(data)
        if 'image_pages' in data:
            return {'pages':[{'page':1,'figures':[{'bbox':[100,100,900,900],
                'label':'Fig. 1','target':True,'reason':'Tc bars'}]}]}
        reading=panel()
        if 'verification_issues' not in data:
            reading['points'][0]['x']=1453
            return {'panels':[reading],'notes':[]}
        if 'observation' not in data:
            box=list(data['crop_bbox']);box[0]+=1
            action={'name':'adjust_image_region','arguments':{'region_id':data['region_id'],
                'bbox_page':box,'reason':'按程序疑点重读该柱','dpi':600}}
            return {'action':action,'_tool_call':{'id':'native-fixed','type':'function',
                'function':{'name':action['name'],'arguments':json.dumps(action['arguments'])}}}
        assert options['images'][1].startswith('data:image/png;base64,')
        assert options['tool_history'][0]['tool_calls'][0]['id']==options['tool_history'][1]['tool_call_id']=='native-fixed'
        if not available[0]:
            raise APIStatusError('fixture',response=httpx.Response(503,request=httpx.Request('POST','https://fixture.invalid')),
                body={'error':{'code':'service_unavailable','request_id':'fixed-503','retry_after_seconds':0}})
        return {'panels':[reading],'notes':[]}
    monkeypatch.setattr(llm,'_complete_json',complete)
    monkeypatch.setattr(llm,'get_llm_config',lambda:SimpleNamespace(model='fixture',base_url='https://fixture.invalid'))
    runtime,context,state=setup_runtime(tmp_path/'runtime',monkeypatch)
    import backend.ingest.model_runtime as runtime_module
    monkeypatch.setattr(runtime_module,'_pause_task_state',lambda task_id,**changes:state.update(status='paused'))
    with context(runtime),pytest.raises(ExecutionStopped):enrich_document(ir,path,source,llm.complete_json)
    assert state['status']=='paused' and len(requests)==8
    assert len(list((tmp_path/'runtime').rglob('failure-*.json')))==5
    available[0]=True
    resumed,context,_=setup_runtime(tmp_path/'runtime',monkeypatch)
    with context(resumed):report=enrich_document(ir,path,source,llm.complete_json)
    assert report['readings']==2 and len(requests)==9
    assert sum('image_pages' in data for data in requests)==1


@pytest.mark.parametrize('fault',['roi','unit'])
def test_spectrum_feedback_uses_new_crop_as_evidence_and_keeps_original_coordinates(tmp_path,fault):
    import base64,hashlib,io
    import pymupdf
    from PIL import Image
    from backend.tests.test_spectra import fixture
    from backend.ingest.document_ir import DocumentIR,DocumentBlock,PageGeometry,content_hash
    from backend.ingest.pdf_regions import region_locator,render_region_image
    from backend.ingest.image_feedback import read_spectrum
    image,correct=fixture();out=io.BytesIO();Image.fromarray(image).save(out,format='PNG')
    path=tmp_path/'spectrum.pdf'
    with pymupdf.open() as pdf:
        page=pdf.new_page(width=200,height=150)
        page.insert_image((0,0,160,100),stream=out.getvalue())
        page.insert_text((10,125),'Fig. 1. Eliashberg function',fontsize=8);pdf.save(path)
    sha=hashlib.sha256(path.read_bytes()).hexdigest()
    ir=DocumentIR(document_id='s',source_file_id='main',source_sha256=sha,parse_profile='complementary',
        pages=[PageGeometry(pdf_page=1,width=200,height=150)],blocks=[DocumentBlock(block_id='fig',
        block_type='figure',pdf_page=1,reading_order=0,bbox=(0,0,160,100),text='Fig. 1',content_hash=content_hash('s'))])
    locator=region_locator(path,'main',sha,1,[0,0,160,100]);rendered=render_region_image(path,locator)
    sx,sy=rendered['width']/160,rendered['height']/100
    curve=correct['curves'][0]
    curve['roi']=[round(value*(sx if i%2==0 else sy)) for i,value in enumerate(curve['roi'])]
    curve['frequency_ticks']=[[x*sx,v] for x,v in curve['frequency_ticks']]
    curve['amplitude_ticks']=[[y*sy,v] for y,v in curve['amplitude_ticks']]
    figure={'image':rendered['png'],'region_locator':locator,'document_ir':ir.model_dump(mode='json'),
        '_pdf_path':str(path),'bbox_pdf_pt':locator['bbox_page']}
    original='data:image/png;base64,'+base64.b64encode(rendered['png']).decode();calls=[]
    def model(prompt,content,**options):
        request=json.loads(content);calls.append(request)
        schema=next(x['function']['parameters'] for x in options['tool_definitions']
                    if x['function']['name']=='report_spectrum_calibration')
        assert 'prefixItems' not in json.dumps(schema)
        pair=schema['$defs']['CurveCalibration']['properties']['amplitude_ticks']['items']
        assert pair=={'type':'array','items':{'type':'number'},'minItems':2,'maxItems':2}
        if len(calls)==1:
            bad=deepcopy(correct);bad['curves'][0]['roi']=[0,0,1,1]
            if fault=='unit':
                bad['curves'][0]['kind']='alpha2f'
                bad['curves'][0]['unit']='arbitrary_units'
            return {'action':{'name':'report_spectrum_calibration','arguments':{'panels':[bad],'issues':[]}}}
        if len(calls)==2:
            assert request['verification_issues']
            return {'action':{'name':'adjust_image_region','arguments':{'region_id':locator['region_id'],
                'bbox_page':[10,5,150,95],'dpi':600,'reason':'核对曲线局部与原刻度'}}}
        assert options['images'][0]==original and len(options['images'])==2
        return {'action':{'name':'report_spectrum_calibration','arguments':{'panels':[correct],'issues':[]}}}
    result=read_spectrum(model,'spectrum',{},figure,[{'state_key':'s1'}],[original])
    assert len(calls)==3 and result['panels'][0]['curves'][0]['roi']==correct['curves'][0]['roi']

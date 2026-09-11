"""证据定位与结果契约，不创建数据库。"""
import copy
import pytest
from fastapi import HTTPException
from backend.ingest import property_evidence as ev


def chunks():
    return [dict(file_id='main', chunk_index=1, content='At 4.29 K we measured a threshold current of 0.12 A.', page_start=5, page_end=5),
            dict(file_id='main', chunk_index=2, content='The transition occurs at 3.78 K.', page_start=5, page_end=5)]


def test_same_page_multiple_chunks_uses_quote():
    match = ev.locate({'page': 5, 'quote': 'transition occurs at 3.78 K.'}, chunks())
    assert match['chunk_index'] == 2
    assert match['page_start'] == 5


def test_stale_chunk_index_relocates_only_by_unique_same_file_quote():
    assert ev.locate({'file_id':'main','chunk_index':99,'quote':'transition occurs at 3.78 K.'}, chunks())['chunk_index'] == 2
    assert ev.locate({'file_id':'other','chunk_index':2,'quote':'transition occurs at 3.78 K.'}, chunks()) is None


def test_fabricated_value_and_ambiguous_source_rejected():
    assert ev.locate({'quote':'transition occurs at 7.19 K.'},chunks()) is None
    duplicated=chunks()+[{**chunks()[1],'file_id':'attachment'}]
    assert ev.locate({'quote':'transition occurs at 3.78 K.'},duplicated) is None


def test_normalization_does_not_change_scientific_values():
    assert ev.locate({'quote':'transition\n occurs  at 3.78 K.'},chunks())
    assert not ev.locate({'quote':'transition occurs at 3.79 K.'},chunks())


def test_legacy_and_multiple_evidence_are_preserved_without_mutation():
    a={'file_id':'main','quote':'a'}; b={'file_id':'main','quote':'b'}
    record={'evidence':a,'evidences':[{'evidence':b},a]}
    before=copy.deepcopy(record)
    assert ev.evidence_list(record)==[a,b]
    assert record==before


def test_semantic_dispute_keeps_valid_source_but_not_supported():
    r={'key':'47','field':'records[47]','label':'SnHg Tc 4.29 K'}
    result=ev.checked_result(r,{'status':'unsupported','reason':'这是测量温度','evidences':[{'quote':chunks()[0]['content']}]},chunks())
    assert result['status']=='unsupported'
    assert result['evidences']
    assert r=={'key':'47','field':'records[47]','label':'SnHg Tc 4.29 K'}


def test_model_cannot_forge_source_to_approve():
    result=ev.checked_result({'key':'47'}, {'status':'supported','evidences':[{'quote':'Tc is 4.29 K'}]},chunks())
    assert result['status']=='missing'
    assert '引句未在所选来源文本中找到' in result['reason']


def test_location_errors_distinguish_missing_file_quote_and_ambiguity():
    assert '没有原文引句' in ev.locate_with_reason({}, chunks())[1]
    assert '没有可读取' in ev.locate_with_reason({'quote': 'q'}, [])[1]
    assert '来源文件不在当前论文' in ev.locate_with_reason({'file_id': 'other', 'quote': 'q'}, chunks())[1]
    duplicate = chunks() + [{**chunks()[1], 'file_id': 'attachment'}]
    assert '匹配多个' in ev.locate_with_reason({'quote': chunks()[1]['content']}, duplicate)[1]
    assert '页码不是有效整数' in ev.locate_with_reason({'quote': chunks()[1]['content'], 'page': 'invalid'}, duplicate)[1]


def test_pending_version_change_rejects_old_result():
    with pytest.raises(HTTPException) as e:
        ev.resolve_results({'version':'current','records':[]},{},1,None,'old')
    assert e.value.detail['code']=='evidence_stale'


def test_api_without_job_cannot_bypass_checks():
    with pytest.raises(HTTPException) as e:
        ev.resolve_results({'target':'paper','target_id':'29','version':'current','records':[{'key':'47'}]},{},1,None,None)
    assert e.value.detail['code']=='evidence_check_required'


def test_page_propagates_across_chunks():
    text='<!-- page: 5 -->\n'+(('Measured current on this page. '*70)+'\n\n')*5
    result=ev.source_chunks(text,'main')
    assert len(result)>1
    assert all(c['page_start']==5 and c['page_end']==5 for c in result)


def test_worker_reports_completed_batches_only_after_model_returns(monkeypatch):
    import json
    from types import SimpleNamespace
    from backend.ingest import upload_tasks
    from backend.rag import llm
    from backend.api.evidence import get_job

    sources = [dict(file_id='main', chunk_index=i, content=f'quote {i} '+ 'x'*24000) for i in range(2)]
    record = dict(key='47', claim={}, evidences=[])
    job = dict(id='test-job', owner=1, status='queued', cached={}, snapshot={
        'target': 'paper', 'target_id': '29', 'version': 'v', 'records': [record], 'chunks': sources})
    observations = []
    class RedisStub:
        def get(self, _key): return json.dumps(job)
        def setex(self, *_args): pass
    monkeypatch.setattr(upload_tasks, 'redis_client', RedisStub)
    monkeypatch.setattr(upload_tasks, 'load_llm_config', lambda _id: SimpleNamespace(model='test'))
    monkeypatch.setattr(upload_tasks, 'delete_llm_config', lambda _id: None)
    monkeypatch.setattr(ev, 'read_job', lambda *_args: job)
    monkeypatch.setattr(ev, 'update_job', lambda _id, **changes: job.update(changes))
    def complete(_system, prompt, **_kwargs):
        public = get_job('test-job', SimpleNamespace(id=1))
        observations.append((public['completed_batches'], public['total_batches'], public['current_batch']))
        source = json.loads(prompt)['sources'][0]
        return {'results': [{'key': '47', 'status': 'supported', 'reason': '原文支持', 'evidences': [
            {'file_id': 'main', 'chunk_index': source['chunk_index'], 'quote': f"quote {source['chunk_index']}"}]}]}
    monkeypatch.setattr(llm, 'complete_json', complete)
    ev.run_evidence_job('test-job')
    assert observations == [(0, 2, 1), (1, 2, 2)]
    public = get_job('test-job', SimpleNamespace(id=1))
    assert public['status'] == 'completed'
    assert public['completed_batches'] == public['total_batches'] == 2

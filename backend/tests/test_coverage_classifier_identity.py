"""覆盖项身份由程序精确回代，不要求模型重抄长散列。"""
import json
from copy import deepcopy
import pytest
from backend.ingest.domain_extraction import classify_uncovered
from backend.rag.structured_output import StructuredOutputError


@pytest.mark.parametrize('unknown', [False, True])
def test_coverage_item_short_identity_roundtrip_and_unknown_rejection(monkeypatch, unknown):
    items=[{'id':'block:'+c*64,'file_id':'main','block_id':c*64,'text':'Original current paper result.'}
           for c in ['a','b']]
    before=deepcopy(items)
    def model(_system, prompt, **options):
        payload=json.loads(prompt)['items']
        ids=[x['id'] for x in payload]
        assert ids==['item_1','item_2']
        assert [x['block_id'] for x in payload]==['a'*64,'b'*64]
        return {'items':[{'id':('item_3' if unknown and i==0 else key),
            'decision':'needs_extraction','category':None,'reason':'Reported numerical result.'}
            for i,key in enumerate(ids)]}
    monkeypatch.setattr('backend.rag.llm.complete_json',model)
    if unknown:
        with pytest.raises(StructuredOutputError):classify_uncovered(items)
    else:
        result=classify_uncovered(items)
        assert [r['id'] for r in result]==[x['id'] for x in items]
        assert [r['block_id'] for r in result]==['a'*64,'b'*64]
    assert items==before

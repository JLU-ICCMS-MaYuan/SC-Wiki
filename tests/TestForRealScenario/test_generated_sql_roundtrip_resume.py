"""旧执行检查点只接受同一AI快照的精确SQL表示，不按数值近似放行。"""
import json
from copy import deepcopy
from types import SimpleNamespace
from contextlib import contextmanager

from backend.ingest import model_runtime, upload_tasks


def test_same_generated_mysql_json_is_recoverable_but_human_changes_are_not(tmp_path,monkeypatch):
    task='a'*32
    original={'paper':{'title':'Generated'},'material_states':[],
              'field_evidence':{'bbox':[208.29600000000002]}}
    stored=deepcopy(original);stored['field_evidence']['bbox'][0]=208.296
    state={'status':'failed','execution_generation':45,'execution_input_hash':'input',
           'execution_draft_hash':model_runtime.digest(original)}
    snapshot={'task_id':task,'paper_id':None,'user_values':None,'ai_values':original,'evidence':{},
              'execution_generation':45,'execution_input_hash':'input'}
    path=tmp_path/'result.json';path.write_text(json.dumps(snapshot))
    monkeypatch.setattr(upload_tasks,'artifact_path',lambda _:path)
    from backend import database
    calls=[]
    @contextmanager
    def session():
        def execute(query,params):
            calls.append(params)
            assert json.loads(next(iter(params.values())))==original
            return SimpleNamespace(scalar_one=lambda:json.dumps(stored))
        yield SimpleNamespace(bind=SimpleNamespace(dialect=SimpleNamespace(name='mysql')),execute=execute)
    monkeypatch.setattr(database,'SessionLocal',session)
    assert model_runtime._unchanged_sql_generated_draft(task,state,stored)
    edited=deepcopy(stored);edited['paper']['title']='Human edit'
    assert not model_runtime._unchanged_sql_generated_draft(task,state,edited)
    edited=deepcopy(stored);edited['field_evidence']['bbox'][0]+=1e-10
    assert not model_runtime._unchanged_sql_generated_draft(task,state,edited)
    before=len(calls)
    assert not model_runtime._unchanged_sql_generated_draft(task,{**state,'execution_generation':46},stored)
    assert not model_runtime._unchanged_sql_generated_draft(task,{**state,'execution_draft_hash':'other'},stored)
    assert len(calls)==before

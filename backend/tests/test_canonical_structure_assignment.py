"""#204：同压力不同优化方法必须由模型结合原文归属，不靠列表顺序。"""
from copy import deepcopy
import pytest


def candidate():
    from backend.services.structure_candidates import build_structure_candidate
    value = build_structure_candidate(structure_format="poscar",
        structure_text="H\n1\n2 0 0\n0 2 0\n0 0 2\nH\n1\nDirect\n0 0 0\n",
        material_state_ref="unassigned:paper", source={"file_id": "main", "page": 1,
        "quote": "The SSCHA relaxed H structure at 100 GPa is listed in Table 1."})
    value["reported_structure"] = {"material": "H", "pressure_value_gpa": 100, "space_group_symbol": "Pm-3m"}
    return value


def test_structure_request_order_survives_process_restart():
    import os
    import json
    import subprocess
    import sys
    code = '''
import json
from backend.ingest.canonical_structure import _assignment_response
rows = [{"file_id":f"file-{i}", "pdf_page":i+1, "source_id":f"source-{i}", "content":f"Original geometry {i}"} for i in range(6)]
pending = [{"sources":[{"file_id":row["file_id"], "page":row["pdf_page"]}]} for row in rows]
def model(prompt, content):
    print(json.dumps([row["source_id"] for row in json.loads(content)["sources"]]))
    return {"done":True,"assignments":[]}
_assignment_response([], pending, rows, model)
'''
    observed = [[json.loads(line)for line in subprocess.check_output([sys.executable, '-c', code], text=True,
                env={**os.environ, 'PYTHONHASHSEED': str(seed)}).splitlines()] for seed in (1, 2, 3)]
    assert observed == [[[f'source-{i}'for i in range(3)],[f'source-{i}'for i in range(3,6)]]] * 3
    assert all([identity for group in run for identity in group]==[f'source-{i}'for i in range(6)]for run in observed)


def test_runtime_request_failure_is_not_swallowed_as_scientific_uncertainty():
    from backend.ingest.canonical_structure import assign_structures
    from backend.ingest.model_runtime import ModelRequestError
    value = draft()
    def unavailable(*args):
        raise ModelRequestError('必要原文超过预算')
    with pytest.raises(ModelRequestError, match='必要原文超过预算'):
        assign_structures(value, [candidate()], [], unavailable)
    assert not any(state.get('structure') for state in value['material_states'])


@pytest.mark.parametrize('explicit_model', [False, True])
def test_upload_assignment_declares_source_contract_and_keeps_geometry(monkeypatch, explicit_model):
    import json
    from backend.ingest import upload_jobs
    from backend.ingest.model_memory import _cites_source_ids
    value, item = draft(), candidate()
    def complete(system, prompt, **options):
        assert _cites_source_ids(options.get('response_schema'))
        assert json.loads(prompt)['candidates'][0]['candidate_id'] == item['candidate_id']
        return {'assignments': [{'candidate_id': item['candidate_id'], 'state_key': 'quantum',
            'structure_optimization': 'sscha', 'geometry_evidence': None, 'new_state': None,
            'source_ids': ['structure-source-0'], 'reason': '原文明确SSCHA结构'}]}
    monkeypatch.setattr(upload_jobs, 'complete_json', complete)
    upload_jobs._bind_structure_candidates(value, [item], model=complete if explicit_model else None)
    assert value['material_states'][1]['structure']['structure_text']
    assert not value['material_states'][0].get('structure')


def test_assignment_reads_methods_page_without_dropping_other_original_sources():
    import json
    from backend.ingest.canonical_structure import assign_structures
    item, value, calls = candidate(), draft(), []
    sources = [{'file_id': 'main', 'pdf_page': 1, 'content': 'H coordinate table at 100 GPa.'},
               {'file_id': 'main', 'pdf_page': 2, 'content': 'The tabulated geometry was SSCHA relaxed.'},
               {'file_id': 'main', 'pdf_page': 3, 'content': 'Other actual original context remains available.'}]
    def model(system, content):
        payload = json.loads(content); calls.append(payload)
        if len(calls) == 1:
            assert len(payload['sources']) == 1
            assert {p['page'] for p in payload['unread_pages']} == {2, 3}
            return {'done': False, 'read_pages': [{'file_id': 'main', 'page': 2}], 'read_source_ids': [], 'search': [], 'assignments': []}
        assert [s['source_id'] for s in payload['sources']] == ['structure-source-0', 'structure-source-1']
        assert payload['unread_pages'][0]['page'] == 3
        return {'done': True, 'assignments': [{'candidate_id': item['candidate_id'], 'state_key': 'quantum',
            'structure_optimization': 'sscha', 'source_ids': ['structure-source-0', 'structure-source-1'],
            'reason': '实际方法页明确该几何为SSCHA优化'}]}
    assign_structures(value, [item], sources, model)
    assert len(calls) == 2 and value['material_states'][1]['structure']['sources']


def test_unread_source_cannot_justify_structure_assignment():
    from backend.ingest.canonical_structure import assign_structures
    item, value = candidate(), draft()
    sources = [{'file_id': 'main', 'pdf_page': 1, 'content': 'H coordinates.'},
               {'file_id': 'main', 'pdf_page': 2, 'content': 'Unread optimization statement.'}]
    assign_structures(value, [item], sources, lambda *_: {'assignments': [{
        'candidate_id': item['candidate_id'], 'state_key': 'quantum', 'structure_optimization': 'sscha',
        'source_ids': ['structure-source-1'], 'reason': '只在未读目录看见的内容不能作依据'}]})
    assert not any(state.get('structure') for state in value['material_states'])
    assert value['structural_extraction_issues']


def test_assignment_read_tools_reject_foreign_file():
    from backend.ingest.canonical_structure import assign_structures
    from backend.ingest.model_runtime import ModelRequestError
    with pytest.raises(ModelRequestError, match='未上传'):
        assign_structures(draft(), [candidate()], [], lambda *_: {'done': False,
            'read_pages': [{'file_id': 'another-upload', 'page': 1}], 'search': [], 'read_source_ids': []})


def draft():
    return {"paper": {}, "material_states": [
        {"state_key": "static", "material": "H", "pressure_value_gpa": 100, "reported_space_group_symbol": "Pm-3m",
         "state_kind": "theoretical", "structure_optimization": "classical_static", "property_modules": []},
        {"state_key": "quantum", "structure_optimization": "sscha", "material": "H", "pressure_value_gpa": 100, "reported_space_group_symbol": "Pm-3m",
         "state_kind": "theoretical", "structure_optimization": "sscha", "property_modules": []}]}


def test_model_assigns_same_pressure_geometry_to_explicit_optimization():
    from backend.ingest.canonical_structure import assign_structures
    c = candidate(); d = draft()
    def model(system, payload):
        return {"assignments": [{"candidate_id": c["candidate_id"], "state_key": "quantum", "structure_optimization": "sscha",
                                "source_ids": ["structure-source-0"], "reason": "原文明确SSCHA优化"}]}
    assign_structures(d, [c], [], model)
    assert not d["material_states"][0].get("structure")
    structure = d["material_states"][1]["structure"]
    assert structure["structure_text"] and structure["sources"] and structure["representations"]
    assert "structure_candidates" not in d


def test_server_assigns_missing_state_identity_before_model_request():
    import json
    from backend.ingest.canonical_structure import assign_structures
    c, d = candidate(), draft()
    d['material_states'][1]['state_key'] = None
    def model(system, payload):
        states = json.loads(payload)['states']
        assert all(state['state_key'] for state in states)
        key = next(state['state_key'] for state in states if state['structure_optimization'] == 'sscha')
        return {'assignments': [{'candidate_id': c['candidate_id'], 'state_key': key,
            'structure_optimization': 'sscha', 'source_ids': ['structure-source-0'], 'reason': '原文SSCHA结构'}]}
    assign_structures(d, [c], [], model)
    assert d['material_states'][0]['state_key'] == 'static'
    assert d['material_states'][1].get('structure')
    assert not d['structural_extraction_issues']


def test_missing_evidence_cannot_become_automatic_assignment():
    from backend.ingest.canonical_structure import assign_structures
    c = candidate(); d = draft()
    assign_structures(d, [c], [], lambda *args: {"assignments": [
        {"candidate_id": c["candidate_id"], "state_key": "quantum", "structure_optimization": "sscha", "source_ids": ["invented"]}]})
    assert not any(s.get("structure") for s in d["material_states"])
    assert d["structural_extraction_issues"]


def test_model_cannot_overwrite_existing_manual_geometry():
    from backend.ingest.canonical_structure import assign_structures
    c = candidate(); d = draft()
    d["material_states"][1]["structure"] = {"structure_format": "cif", "structure_text": "user-owned", "user_note": "手工输入"}
    before = deepcopy(d["material_states"][1]["structure"])
    assign_structures(d, [c], [], lambda *args: {"assignments": [
        {"candidate_id": c["candidate_id"], "state_key": "quantum", "structure_optimization": "sscha",
         "source_ids": ["structure-source-0"], "reason": "SSCHA"}]})
    assert d["material_states"][1]["structure"] == before
    assert d["structural_extraction_issues"][0]["state_key"] == "quantum"


def test_nearby_sscha_cell_cannot_reclassify_static_geometry():
    from backend.ingest.canonical_structure import assign_structures
    c = candidate(); c["reported_structure"]["cell_parameters"] = {"a": 2, "b": 2, "c": 2}
    d = draft()
    assign_structures(d, [c], [], lambda *args: {"assignments": [{
        "candidate_id": c["candidate_id"], "state_key": "quantum", "structure_optimization": "sscha", "source_ids": ["structure-source-0"],
        "geometry_evidence": {"source_id": "structure-source-0", "cell_parameters": {"a": 2.03, "c": 2.03}},
        "reason": "晶格参数接近"}]})
    assert not any(s.get("structure") for s in d["material_states"])
    assert "晶格参数" in d["structural_extraction_issues"][0]["reason"]


def test_model_static_classification_cannot_write_to_sscha_state():
    from backend.ingest.canonical_structure import assign_structures
    c = candidate(); d = draft()
    assign_structures(d, [c], [], lambda *args: {"assignments": [{
        "candidate_id": c["candidate_id"], "state_key": "quantum",
        "structure_optimization": "classical_static", "source_ids": ["structure-source-0"],
        "reason": "静态结构，但给了错误目标"}]})
    assert not any(s.get("structure") for s in d["material_states"])
    assert "优化方法" in d["structural_extraction_issues"][0]["reason"]



def test_verified_manual_replacement_does_not_reuse_stale_assignment_failure():
    from backend.ingest.canonical_structure import structure_from_candidate
    from backend.ingest.scientific_evidence import augment_upload
    d = draft()
    structure = structure_from_candidate(candidate())
    d['material_states'][1]['structure'] = structure
    d['structural_extraction_issues'] = [{'state_key': 'quantum', 'reason': '先前模型归属失败'}]
    records = []
    augment_upload(d, records, {structure['structure_hash']: {'submitted_by_user_id': 2}})
    current = next(row for row in records if row.get('kind') == 'structure' and row.get('state_key') == 'quantum')
    assert '_structure_issue' not in current
    assert not current.get('passed')
    assert d['structural_extraction_issues'][0]['reason'] == '先前模型归属失败'


def test_upload_assignment_only_exposes_uploaded_page_and_stable_identity_choices(monkeypatch):
    import json
    from backend.ingest import upload_jobs
    from backend.rag.structured_output import validate_output,StructuredOutputError
    value,item=draft(),candidate();seen=[]
    def complete(system,content,**options):
        payload=json.loads(content);schema=options["response_schema"];seen.append(schema)
        base={"done":False,"read_pages":[{"file_id":"not-an-uploaded-file","page":2}],
              "read_source_ids":[],"search":[],"assignments":[]}
        with pytest.raises(StructuredOutputError):validate_output(base,schema)
        base["read_pages"]=[{"file_id":"main","page":99}]
        with pytest.raises(StructuredOutputError):validate_output(base,schema)
        base["read_pages"]=[{"file_id":"main","page":2}]
        validate_output(base,schema)
        return {"done":True,"read_pages":[],"read_source_ids":[],"search":[],"assignments":[]}
    upload_jobs._bind_structure_candidates(value,[item],sources=[{"file_id":"main","pdf_page":2,"content":"SSCHA optimization context"}],model=complete)
    assert seen


def test_assignment_budget_partitions_candidates_without_losing_original_sources(monkeypatch):
    import json
    from backend.ingest.canonical_structure import _assignment_response
    from backend.ingest import model_memory
    from backend.ingest.model_memory import ContextBudgetError
    calls=[]
    def budget(request,**_):
        if len(json.loads(request["user_prompt"])["candidates"])>1:raise ContextBudgetError("隔离模拟既有预算门")
        return request
    monkeypatch.setattr(model_memory,"prepare_fixed_request",budget)
    rows=[{"file_id":"main","pdf_page":1,"source_id":"s1","content":"all original row 1"},
          {"file_id":"main","pdf_page":2,"source_id":"s2","content":"all original row 2"}]
    candidates=[{"candidate_id":"c1","sources":[{"file_id":"main","page":1}]},
                {"candidate_id":"c2","sources":[{"file_id":"main","page":1}]}]
    def model(prompt,content):
        body=json.loads(content);calls.append(body)
        assert len(body["candidates"])==1
        assert body["sources"]==[rows[0]]
        assert body["unread_pages"][0]["page"]==2
        return {"done":True,"read_source_ids":[],"search":[],"read_pages":[],
          "assignments":[{"candidate_id":body["candidates"][0]["candidate_id"],"reason":"原归属保留"}]}
    answer,sources=_assignment_response([],candidates,rows,model)
    assert [a["candidate_id"]for a in answer["assignments"]]==["c1","c2"]
    assert sources=={"s1":rows[0]} and len(calls)==2


def test_page_fetch_choices_are_unread_and_completed_reports_can_name_read_sources():
    from backend.ingest.canonical_structure import assignment_response_schema
    from backend.rag.structured_output import validate_output,StructuredOutputError
    payload={"sources":[{"file_id":"main","pdf_page":1,"source_id":"read"}],
      "unread_pages":[{"file_id":"main","page":2}],"unread_sources":[{"source_id":"unread","file_id":"main","page":2}],
      "candidates":[{"candidate_id":"c"}],"states":[{"state_key":"s"}]}
    schema=assignment_response_schema(payload)
    base={"done":False,"read_pages":[{"file_id":"main","page":1}],"read_source_ids":[],"search":[],"assignments":[]}
    with pytest.raises(StructuredOutputError):validate_output(base,schema)
    base["read_pages"]=[{"file_id":"main","page":2}];base["read_source_ids"]=["read"]
    # 混合来源集合继续合法；运行时仍要求未完成的读取动作至少带来一项新原文。
    validate_output(base,schema)
    base["read_source_ids"]=["unread"];validate_output(base,schema)
    base["read_source_ids"]=["invented"]
    with pytest.raises(StructuredOutputError):validate_output(base,schema)
    done={"done":True,"read_pages":[],"read_source_ids":["read"],"search":[],"assignments":[{"candidate_id":"c","state_key":"s",
      "structure_optimization":"unknown","geometry_evidence":None,"new_state":None,"source_ids":["read"],"reason":"原依据"}]}
    validate_output(done,schema)


def test_extraction_local_row_alias_cannot_be_mistaken_for_assignment_source_identity():
    from backend.ingest.canonical_structure import assign_structures
    import json
    value,item=draft(),candidate()
    item["reported_structure"]["atomic_positions"]=[{"element":"H","coordinates":[0,0,0],"source_id":"structure-source-0"}]
    original=deepcopy(item)
    sources=[{"file_id":"main","pdf_page":1,"content":"Original coordinate and method context"}]
    def model(prompt,content):
        body=json.loads(content)
        local=body["candidates"][0]["reported_structure"]["atomic_positions"][0]
        assert local["coordinates"]==[0,0,0]
        assert local["source_id"]!="structure-source-0"
        assert local["source_id"] not in {s["source_id"]for s in body["sources"]}
        assert "candidate-local" in local["source_id"]
        return {"done":True,"assignments":[{"candidate_id":item["candidate_id"],"state_key":"quantum",
            "structure_optimization":"sscha","source_ids":["structure-source-0"],"reason":"实际全局原文支持SSCHA"}]}
    assign_structures(value,[item],sources,model)
    assert item["reported_structure"]==original["reported_structure"]
    assert value['material_states'][1].get('structure')


def test_assignment_small_groups_do_not_resend_unrelated_material_states():
    import json
    from backend.ingest.canonical_structure import _assignment_response
    states=[{"state_key":"s"+str(i),"material":m}for i,m in enumerate(["H","He","Li","Be","B"])]
    pending=[{"candidate_id":"c"+str(i),"reported_structure":{"material":s["material"]},
              "sources":[{"file_id":"main","page":1}]}for i,s in enumerate(states)]
    rows=[{"file_id":"main","pdf_page":1,"source_id":"source","content":"Unchanged complete original geometry context"}]
    calls=[]
    def model(prompt,content):
        body=json.loads(content);calls.append(body)
        assert len(body["candidates"])<=3
        needed={c["reported_structure"]["material"]for c in body["candidates"]}
        assert {s["material"]for s in body["states"]}==needed
        assert body["sources"]==rows
        return {"done":True,"assignments":[{"candidate_id":c["candidate_id"],"reason":"保留归属"}for c in body["candidates"]]}
    answer,_=_assignment_response(states,pending,rows,model)
    assert len(calls)==2
    assert [r["candidate_id"]for r in answer["assignments"]]==["c0","c1","c2","c3","c4"]

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


def test_runtime_request_failure_is_not_swallowed_as_scientific_uncertainty():
    from backend.ingest.canonical_structure import assign_structures
    from backend.ingest.model_runtime import ModelRequestError
    value = draft()
    def unavailable(*args):
        raise ModelRequestError('必要原文超过预算')
    with pytest.raises(ModelRequestError, match='必要原文超过预算'):
        assign_structures(value, [candidate()], [], unavailable)
    assert not any(state.get('structure') for state in value['material_states'])


def test_upload_assignment_declares_source_contract_and_keeps_geometry(monkeypatch):
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
    upload_jobs._bind_structure_candidates(value, [item])
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

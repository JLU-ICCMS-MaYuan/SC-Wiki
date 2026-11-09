"""正式Worker的IR来源门和分组执行接线；模型与存储边界由固定夹具替代。"""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path

import pytest


def test_worker_uses_group_fill_source_gate_review_and_save(tmp_path, monkeypatch, db_session):
    from backend.ingest import upload_jobs as jobs, upload_tasks, state_inventory, material_batches, property_evidence, paper_first
    calls = []
    class Checked(Exception): pass
    real = material_batches.process_material_groups
    def grouped(draft, sources, model, **options):
        result = real(draft, sources, model, **options)
        assert result['claims'] and all(c.status == 'validated' for c in result['claims'])
        assert result['filling_report']['status'] == 'completed'
        assert calls == ['review', 'save']
        raise Checked()
    monkeypatch.setattr(material_batches, 'process_material_groups', grouped)
    monkeypatch.setattr(state_inventory, 'plan_states', lambda *_a, **_k: None)
    monkeypatch.setattr(paper_first, 'persist_paper', lambda *_: calls.append('save'))
    def reviewed(task, draft, owner, **options):
        from backend.ingest.document_claims import claims_from_candidates
        from backend.ingest.document_ir import DocumentIR
        assert options['field_scope'] == 'states'
        assert options['state_keys'] == [draft['material_states'][0]['state_key']]
        documents = {ir.source_file_id: ir for ir in [DocumentIR.model_validate_json(p.read_text())
            for p in (jobs.artifact_directory(task)/'document_ir').glob('*.json')]}
        assert all(c.status == 'validated' for c in claims_from_candidates(draft, documents))
        calls.append('review')
        return {}
    monkeypatch.setattr(property_evidence, 'generate_upload_suggestions', reviewed)
    def selected(task):
        from backend.ingest.parsing_workflows import CURRENT, BINDING
        jobs.update_state(task, **{BINDING: CURRENT.binding()})
        paper = jobs._normalize_draft({'paper': {'title':'Reviewed paper', 'paper_type':'theoretical',
            'year':2026, 'research_materials':['LaH10']}, 'material_states':[]})
        jobs._atomic_write_json(jobs.artifact_directory(task)/'paper-stage.json', {'completed':True,'draft':paper})
        original = jobs.complete_json
        def model(prompt, body, **options):
            try: value = json.loads(body)
            except ValueError: value = None
            if isinstance(value, dict) and 'image_pages' in value:
                return {'pages':[{'page':p,'figures':[]} for p in value['image_pages']]}
            return original(prompt, body, **options)
        monkeypatch.setattr(jobs, 'complete_json', model)
        return jobs._process_conventional_upload_task(task)
    monkeypatch.setattr(jobs, '_process_upload_task', selected)
    path = Path(__file__).parents[1]/'01_decentralized_uploading'/'test_issue139_workflow.py'
    monkeypatch.syspath_prepend(str(path.parent))
    spec = importlib.util.spec_from_file_location('group_worker_fixture', path)
    helper = importlib.util.module_from_spec(spec); spec.loader.exec_module(helper)
    with pytest.raises(Checked):
        helper.test_worker_finishes_direct_claim_gate_before_common_methods_fill(tmp_path, monkeypatch, db_session)

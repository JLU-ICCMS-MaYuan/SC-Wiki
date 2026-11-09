"""#211：真实Worker交给状态规划的来源必须仍能在同一PDF IR定位。"""
import importlib.util
import json
from pathlib import Path

import pytest


def test_worker_inventory_retains_ir_identity(tmp_path, monkeypatch, db_session):
    from backend.ingest import state_inventory, upload_jobs
    from backend.ingest.document_ir import DocumentIR
    from backend.ingest.document_claims import claims_from_candidates

    class Checked(Exception):
        pass

    planner = state_inventory.plan_states

    def inspect_planning(draft, chunks, model, **kwargs):
        def sourced(_, prompt, **options):
            request = json.loads(prompt)
            candidate = request['candidates'][0]
            source = request['sources'][0]['source_id']
            return {'states': [{'values': {k: candidate.get(k) for k in state_inventory.FIELDS},
                                'source_ids': [source], 'reason': '本PDF报告的材料及压力'}],
                    'assignments': [{'candidate_state_key': candidate['state_key'], 'target_index': 0,
                                     'status': 'supported', 'source_ids': [source], 'reason': '同一候选原记录'}]}
        planner(draft, chunks, sourced, **kwargs)
        root = upload_jobs.artifact_directory('a' * 32)
        documents = {p.stem: DocumentIR.model_validate_json(p.read_text()) for p in (root/'document_ir').glob('*.json')}
        claims = claims_from_candidates(draft, documents)
        assert claims and all(c.status == 'validated' for c in claims), '状态规划不能把实际IR身份换成Markdown临时块'
        raise Checked()

    monkeypatch.setattr(state_inventory, 'plan_states', inspect_planning)
    # #212已把类型选择放到外层；本回归验证实际常规Worker到原IR的交接。
    def selected_conventional(task_id):
        from backend.ingest.parsing_workflows import CURRENT, BINDING
        upload_jobs.update_state(task_id, **{BINDING: CURRENT.binding()})
        original_model = upload_jobs.complete_json
        def image_aware_model(prompt, content, **options):
            try:
                payload = json.loads(content)
            except ValueError:
                payload = None  # 正式分段请求有章节/页码前缀，沿原固定模型处理。
            if isinstance(payload, dict) and 'image_pages' in payload:
                # 此固定PDF只有文字/表格；新增逐页图盘点仍返回完整页面回执。
                return {'pages': [{'page': page, 'figures': []} for page in payload['image_pages']]}
            return original_model(prompt, content, **options)
        monkeypatch.setattr(upload_jobs, 'complete_json', image_aware_model)
        return upload_jobs._process_conventional_upload_task(task_id)
    monkeypatch.setattr(upload_jobs, '_process_upload_task', selected_conventional)
    path = Path(__file__).parents[1]/'01_decentralized_uploading'/'test_issue139_workflow.py'
    monkeypatch.syspath_prepend(str(path.parent))
    spec = importlib.util.spec_from_file_location('worker_handoff_fixture', path)
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    with pytest.raises(Checked):
        helper.test_worker_finishes_direct_claim_gate_before_common_methods_fill(tmp_path, monkeypatch, db_session)

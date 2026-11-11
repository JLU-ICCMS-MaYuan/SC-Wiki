"""原PDF相关字段的新模型核对及人工方向隔离保存；不是五阶段业务黑盒。"""
from pathlib import Path
from copy import deepcopy
import hashlib
import json
import os
import tempfile
from dotenv import load_dotenv


def main():
    import argparse
    parser = argparse.ArgumentParser(); parser.add_argument('--case', choices=['lah9', 'sc-h10'], default='lah9')
    case = parser.parse_args().case
    load_dotenv('.env')
    root = Path(__file__).parent/'runs/20261111-peng2017-flash-clean-01/human-question-live'
    root.mkdir(exist_ok=True)
    if case == 'sc-h10':
        root = root/'sc-h10'; root.mkdir(exist_ok=True)
    from datetime import datetime, timezone
    root = root / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    root.mkdir()
    with tempfile.TemporaryDirectory(prefix='scwiki-humanq-live-') as temporary:
        os.environ['DATABASE_URL'] = 'sqlite:///' + temporary + '/isolated.sqlite'
        from backend.database import Base, engine, SessionLocal
        from backend import models, workdraft_models
        from backend.ingest import manual_evidence, human_questions as hq
        from backend.ingest.property_evidence import complete_snapshot
        from backend.ingest.model_review import review_fields, bind_result
        from backend.ingest.field_review import bind_support_versions
        from backend.ingest.scientific_evidence import save_results
        from backend.rag.llm_context import catalog_config, set_llm_config, reset_llm_config
        from backend.rag.llm import complete_json
        import pymupdf
        Base.metadata.create_all(engine)
        with SessionLocal.begin() as db:
            db.add(models.User(id=2, email='isolated@example.invalid', username='isolated',
                real_name='Isolated verification', password_hash='not-a-real-credential', is_approved=True))
        folder = Path(__file__).parent/'runs/20261106-peng2017/sources'
        files = []; chunks = []
        for file_id, role, name in [('main', 'main', '2017 YHn LaHn-彭枫.pdf'),
                                   ('si', 'supplementary', '2017 YHn LaHn-彭枫 Supplementary.pdf')]:
            path = folder/name
            files.append({'file_id': file_id, 'role': role, 'kind': 'pdf', 'stored_path': str(path.resolve()),
                          'size': path.stat().st_size, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
            with pymupdf.open(path) as pdf:
                chunks.extend({'file_id': file_id, 'file_role': role, 'chunk_index': index, 'page_start': index+1,
                    'page_end': index+1, 'content': page.get_text()} for index, page in enumerate(pdf))
        row = {'key': 'phase', 'item_key': 'phase', 'kind': 'field', 'required': True,
            'field': 'material_states[0].reported_space_group_symbol', 'state_key': 'lah9-50',
            'label': 'LaH9 at 50 GPa 的空间群', 'current_value': 'Cc',
            'claim': {'value': 'Cc', 'context': {'material': 'LaH9', 'pressure_value_gpa': 50}},
            'provenance': {'review_target': '核对正文Fig.1(c)、Fig.4与SI表S1的同压力关系，必须读相关原图；不同压力的声子谱不互相证明'}}
        if case == 'sc-h10':
            row.update(state_key='sch10-300', label='ScH10 at 300 GPa 的空间群', current_value='P63/mmc',
                claim={'value': 'P63/mmc', 'context': {'material': 'ScH10', 'pressure_value_gpa': 300}},
                provenance={'review_target': '核对SI表S1与SI Fig.S28(i)的同材料、同压力物相关系，不能把一相声子用作另一相晶胞的证明'})
        snapshot = bind_support_versions(complete_snapshot('upload', 'isolated-live', [row], chunks, {}))
        state = {'task_id': 'isolated-live', 'user_id': 2, 'status': 'summarizing', 'files': files,
                 'human_questions_policy': {'version': 1, 'enabled': True}}
        calls = []; questions = []
        def model(prompt, content, **options):
            index = len(calls)+1
            (root/f'request-{index}.json').write_text(json.dumps({'prompt': prompt, 'content': content,
                'tools': options.get('tool_definitions')}, ensure_ascii=False))
            value = complete_json(prompt, content, **options)
            calls.append(value)
            (root/f'response-{index}.json').write_text(json.dumps(value, ensure_ascii=False))
            print('model_request', index, (value.get('action') or {}).get('name', 'results'), flush=True)
            return value
        def report(route, **kwargs):
            with SessionLocal.begin() as db:
                question = hq.append_question(db, state, route, **kwargs)
            questions.append(question); return question
        token = set_llm_config(catalog_config('LLM1'))
        try:
            first = review_fields(snapshot['records'], chunks, model=model, model_name='server:LLM1/deepseek-flash',
                                  manifest=files, on_human_question=report)
            (root/'first-results.json').write_text(json.dumps(first, ensure_ascii=False))
            if questions:
                question = questions[0]
                with SessionLocal.begin() as db:
                    hq.answer_question(db, state, 2, question['question_id'], {'answer_id': 'prior-user-adjudication',
                        'choice_id': 'manual', 'prompt_revision': question['prompt_revision'],
                        'target_token': question['target_token'], 'expected_queue_revision': 1,
                        'manual_text': ('ScH10只录入P63/mmc结构，不录入Cmcm结构；保留两处原始标注及冲突，不以Cmcm声子证明P63/mmc晶胞。'
                            if case == 'sc-h10' else 'LaH9只保留Cc、50 GPa这一材料状态，不根据Fig.1(c)拆出P63/mmc状态；保留图中原始标注及与附件冲突的说明。'),
                        'reason': '沿用本轮用户结合附件结构、计算对象及稳定压力作出的科学裁定；不同压力声子仍保留适用限制。'},
                        current_targets={r['item_key']: r for r in snapshot['records']})
                with SessionLocal() as db:
                    accepted = deepcopy(db.get(models.ScientificUploadDraft, state['task_id']).state)
                second = review_fields(snapshot['records'], chunks, model=model, model_name='server:LLM1/deepseek-flash',
                    manifest=files, human_context=hq.answer_context(accepted, snapshot['records']))
                assert not any(v.get('review_error') for v in second.values()), second
                with SessionLocal.begin() as db:
                    hq.persist_directions(db, accepted, snapshot, {'phase'}, model_read=True)
                refreshed = bind_support_versions(deepcopy(snapshot))
                final = {r['key']: bind_result(r, second[r['key']], chunks) for r in refreshed['records']}
                with SessionLocal.begin() as db:
                    save_results(db, refreshed, final, 2)
                with SessionLocal() as db:
                    evidence = manual_evidence.read_field(db, refreshed, refreshed, 'phase', include_history=False)
                    field = db.get(manual_evidence.ScientificManualEvidence, evidence['id'])
                    content = manual_evidence._read_file(field.id, field.items[0]).decode()
                    assert evidence['items'] and ('ScH10只录入P63/mmc' if case == 'sc-h10' else 'LaH9只保留Cc') in content
                (root/'after-answer-results.json').write_text(json.dumps(final, ensure_ascii=False))
            report_value = {'scope': '原PDF相关字段新Flash核对、真实问题与既有用户裁定的隔离保存重读；非整篇黑盒',
                'calls': len(calls), 'questions': len(questions), 'first_status': {k:v['status'] for k,v in first.items()},
                'human_material_saved_and_reread': bool(questions), 'business_database_touched': False,
                'source_hashes': {f['file_id']: f['sha256'] for f in files}}
            (root/'result.json').write_text(json.dumps(report_value, ensure_ascii=False, indent=2)); print(report_value, flush=True)
        finally: reset_llm_config(token)


if __name__ == '__main__': main()

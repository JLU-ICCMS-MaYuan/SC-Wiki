"""独立Redis/SQLite/RQ/API恢复验证；不触及业务库，不伪装成论文黑盒。"""
from pathlib import Path
import json
import os
import socket
import subprocess
import tempfile
import time


def pause_stage(task_id):
    from backend.ingest.model_runtime import start_runtime, execution_context, ExecutionStopped
    from backend.ingest.human_questions import pause_for_questions
    from backend.ingest.upload_tasks import get_state, update_state
    runtime = start_runtime(task_id)
    try:
        with execution_context(runtime):
            update_state(task_id, status='extracting')
            update_state(task_id, status='summarizing')
            pause_for_questions(task_id)
    except ExecutionStopped:
        if get_state(task_id)['status'] == 'pausing':
            return update_state(task_id, status='paused', processing_status='paused')
        raise


def main():
    report_path = Path(__file__).parent/'runs/20261111-peng2017-flash-clean-01/human-question-runtime.json'
    with tempfile.TemporaryDirectory(prefix='scwiki-humanq-') as root:
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0)); port = sock.getsockname()[1]
        os.environ.update(DATABASE_URL='sqlite:///' + root + '/isolated.sqlite',
            REDIS_URL=f'redis://127.0.0.1:{port}/0', SC_WIKI_DATA_DIR=root,
            JWT_SECRET_KEY='isolated-runtime-test-placeholder-only')
        server = subprocess.Popen(['/Users/mayuan/software/miniconda3/envs/sc-wiki/bin/redis-server',
            '--bind', '127.0.0.1', '--port', str(port), '--save', '', '--appendonly', 'no', '--dir', root],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            from redis import Redis
            connection = Redis(host='127.0.0.1', port=port)
            for _ in range(100):
                try:
                    if connection.ping(): break
                except ConnectionError: pass
                except Exception: pass
                time.sleep(.05)
            from backend.database import Base, engine, SessionLocal
            from backend import models, workdraft_models
            from backend.ingest import manual_evidence, human_questions as hq, upload_tasks as tasks
            from backend.rag.llm_context import LlmConfig, set_llm_config, reset_llm_config
            from backend.ingest.model_runtime import resume_task, current_execution
            from rq import Queue, SimpleWorker
            from fastapi import FastAPI
            from fastapi.testclient import TestClient
            from backend.api.upload_tasks import router
            from backend.security import get_current_user
            from backend.rag.llm_context import request_llm_config
            from types import SimpleNamespace
            Base.metadata.create_all(engine)
            config = LlmConfig(provider='openai', base_url='https://api.openai.com/v1', model='isolated-probe',
                api_key='nonfunctional-test-placeholder', user_supplied=True)
            token = set_llm_config(config)
            try:
                state = tasks.create_task(2, filename='isolated-only.pdf')
                task_id = state['task_id']
                tasks.save_llm_config(task_id, config)
                tasks.update_state(task_id, status='queued')
                target = {'candidate_id': 'candidate', 'reading_id': 'reading', 'content_hash': 'value', 'source_hash': 'source'}
                tasks.update_state(task_id, human_question_candidates={'candidate': target})
                route = {'kind': 'human_required', 'requires_human': True, 'reason_code': 'source_conflict',
                    'reason': '隔离固定双来源冲突', 'checked_context': '固定回放，不冒充真实论文提取',
                    'target_refs': [target], 'source_refs': [{'file_id': 'main', 'content': 'phase A'}, {'file_id': 'si', 'content': 'phase B'}]}
                q = hq.report_question(task_id, route, recommendation='保留附件物相及两侧原依据')
                queue = Queue('isolated-humanq', connection=connection)
                job = queue.enqueue('verify_human_question_runtime.pause_stage', task_id)
                worker = SimpleWorker([queue], connection=connection)
                worker.work(burst=True, logging_level='WARNING')
                assert job.get_status(refresh=True) == 'finished'
                paused = tasks.get_state(task_id)
                assert paused['status'] == 'paused' and paused['pause_reason'] == 'human_questions'
                # 缓存真正丢失后从SQL重建，再经真实HTTP接口读答。
                connection.delete(tasks.task_key(task_id))
                assert tasks.get_state(task_id)['status'] == 'paused'
                app = FastAPI(); app.include_router(router)
                actor = [SimpleNamespace(id=2, role='user', is_approved=True)]
                app.dependency_overrides[get_current_user] = lambda: actor[0]
                app.dependency_overrides[request_llm_config] = lambda: config
                client = TestClient(app)
                endpoint = f'/api/upload-tasks/{task_id}/human-questions'
                view = client.get(endpoint); assert view.status_code == 200
                payload = {'answer_id': 'answer', 'prompt_revision': q['prompt_revision'], 'target_token': q['target_token'],
                    'expected_queue_revision': view.json()['data']['queue_revision'], 'choice_id': 'recommended'}
                response = client.post(endpoint + '/' + q['question_id'] + '/answers', json=payload)
                assert response.status_code == 200, response.text
                assert response.json()['data']['accepted'] and response.json()['data'].get('resume') == 'queued', response.text
                current = tasks.get_state(task_id); resumed_job = tasks.upload_queue().fetch_job(current['job_id'])
                assert resumed_job.func_name == 'backend.ingest.upload_jobs.process_upload_task'
                count = tasks.upload_queue().count
                duplicate = client.post(endpoint + '/' + q['question_id'] + '/answers', json=payload)
                assert duplicate.status_code == 200 and tasks.upload_queue().count == count
                actor[0] = SimpleNamespace(id=3, role='superadmin', is_approved=True)
                assert client.get(endpoint).status_code == 403
                assert client.post(endpoint + '/' + q['question_id'] + '/answers', json=payload).status_code == 403
                report = {'scope': '隔离真实Redis/RQ暂停释放、SQL恢复、HTTP读答及正式续跑入队；未执行论文提取或第二次业务Worker',
                    'pause_job_finished': True, 'paused_reason': paused['pause_reason'], 'cache_deleted_and_sql_restored': True,
                    'answer_accepted': True, 'resumed_production_job': resumed_job.func_name,
                    'duplicate_answer_did_not_enqueue_again': True, 'other_superadmin_forbidden': True,
                    'business_database_touched': False, 'model_calls': 0}
                report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2))
                print(json.dumps(report, ensure_ascii=False))
            finally: reset_llm_config(token)
        finally:
            server.terminate(); server.wait(timeout=10)


if __name__ == '__main__':
    main()

"""只读观察本轮真实任务，保存安全状态与实际 Worker 信息。"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv('.env')

from backend.ingest.upload_tasks import get_state, upload_queue
from rq import Worker

ROOT = Path(__file__).resolve().parent
ACTIVE = ROOT / 'active-task.json'
TASK_ID = json.loads(ACTIVE.read_text())['task_id'] if ACTIVE.exists() else '90427eb91a05495fb671a705b5ece82f'


def observe(browser=False):
    state = get_state(TASK_ID) or {}
    queue = upload_queue()
    record = {
        'at': datetime.now(timezone.utc).isoformat(),
        'task': {key: state.get(key) for key in (
            'task_id', 'status', 'stage', 'reading_state', 'completed_chunks',
            'total_chunks', 'processing_error', 'error_code', 'job_id',
            'execution_model', 'model_activity', 'revision',
        )},
        'queue_count': queue.count,
        'workers': [
            {'name': worker.name, 'state': worker.state,
             'job_id': worker.get_current_job_id(),
             'last_heartbeat': str(worker.last_heartbeat)}
            for worker in Worker.all(connection=queue.connection)
        ],
    }
    if browser:
        from operate import act
        record['page'] = act(
            'safari', 'http://127.0.0.1:5173/upload/tasks/' + TASK_ID,
            'return {url:location.href,text:document.body.innerText};', window=7839,
        )
    output = ROOT / ('observe-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '.json')
    output.write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n')
    activity = record['task'].pop('model_activity') or {}
    print(json.dumps({
        'evidence': output.name, **record['task'],
        'activity': {key: value for key, value in activity.items() if key != 'history'},
        'registered_workers': len(record['workers']),
    }, ensure_ascii=False))


if __name__ == '__main__':
    observe('--browser' in sys.argv)

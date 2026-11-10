"""只读跟踪本轮当前任务，记录状态变化；不执行恢复或业务动作。"""
from dotenv import load_dotenv
load_dotenv('.env')
from datetime import datetime, timezone
from pathlib import Path
import json, time
from backend.ingest.upload_tasks import get_state

ROOT = Path(__file__).resolve().parent
TASK = json.loads((ROOT / 'active-task.json').read_text())['task_id']
previous, emitted = None, 0
while True:
    try:
        state = get_state(TASK) or {}
        activity = state.get('model_activity') or {}
        value = {key: state.get(key) for key in ('status', 'stage', 'job_id', 'processing_phase',
            'material_batch', 'processing_error', 'suggestions_completed', 'suggestions_total')}
        value['activity'] = {key: activity.get(key) for key in ('phase', 'status', 'attempt', 'error')}
        signature = json.dumps(value, sort_keys=True, ensure_ascii=False)
        if signature != previous or time.monotonic() - emitted >= 45:
            value.update(at=datetime.now(timezone.utc).isoformat(), task_id=TASK,
                request_elapsed_seconds=round(time.time()-activity.get('started_at',time.time())),
                execution_heartbeat_age_seconds=round(time.time()-state.get('execution_heartbeat',time.time())))
            with (ROOT / 'watch-progress.jsonl').open('a') as stream:
                stream.write(json.dumps(value, ensure_ascii=False) + '\n')
            print(json.dumps(value, ensure_ascii=False), flush=True)
            previous, emitted = signature, time.monotonic()
        if (state.get('status') in {'failed', 'paused', 'cancelled', 'submitted', 'ready', 'succeeded'}
                or state.get('stage') == 'ready'):
            break
    except Exception as error:
        print(json.dumps({'at':datetime.now(timezone.utc).isoformat(),
            'read_error_type':type(error).__name__, 'task_id':TASK},ensure_ascii=False), flush=True)
    time.sleep(5)

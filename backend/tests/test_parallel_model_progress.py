"""并发中的接收事件必须保留自己分段的文件和页码。"""
from contextlib import contextmanager
import json
import threading
import time

from backend.ingest.model_runtime import ModelRuntime, execution_context, current_execution
from backend.ingest.parallel_extraction import ordered_extract
from backend.rag.llm import call_phase, _call_scope


def test_receiving_event_does_not_borrow_other_completed_segment(tmp_path, monkeypatch):
    from backend.ingest import model_memory
    monkeypatch.setattr(model_memory, 'prepare_request', lambda request, *a, **kw: request)
    monkeypatch.setattr(model_memory, 'validate_context_output', lambda *a: None)
    state = {'status': 'reading', 'execution_generation': 1}
    lock = threading.RLock()
    runtime = ModelRuntime('a' * 32, 1, tmp_path, lambda: dict(state),
        lambda **changes: state.update(changes), lambda: lock, identity={'model': 'fixture'})
    def complete(*_a, **options):
        name = _call_scope.get()['filename']
        if name == 'A.pdf':
            options['on_partial']('a received token')
            time.sleep(.45)
        return {'filename': name}
    def extract(index, name):
        with call_phase('chunk_extraction', filename=name, pages=[index + 1]):
            return current_execution().call(complete, 'source facts', json.dumps({'segment': name}))
    with execution_context(runtime):
        result = ordered_extract(['A.pdf', 'B.pdf'], extract)
    assert [r['filename'] for r in result] == ['A.pdf', 'B.pdf']
    receiving = [json.loads(line) for line in (tmp_path / 'events.jsonl').read_text().splitlines()
                 if json.loads(line)['status'] == 'receiving']
    assert receiving and all(e['filename'] == 'A.pdf' and e['pages'] == [1] for e in receiving)

import copy
from contextlib import nullcontext
from types import SimpleNamespace

import pytest
from backend.api import evidence as api
from backend.ingest import property_evidence as ev
from backend.ingest import upload_tasks
from backend.ingest.scientific_evidence import record_claim


@pytest.mark.parametrize('changed', [False, True])
def test_evidence_writeback_preserves_version_and_never_overwrites_concurrent_edit(monkeypatch, changed):
    record = dict(record_key='tc', record_type='measured_tc', name_raw='Tc', value_kind='number',
                  value_number=3.78, value_raw='3.78', unit_raw='K')
    draft = {'paper': {'title': 'original'}, 'material_states': [{
        'state_key': 'sn', 'material': 'Sn', 'property_modules': [{
            'module_key': 'module-tc', 'module_code': 'superconductive_properties', 'records': [record],
        }],
    }]}
    chunks = [dict(file_id='main', chunk_index=0, content='The transition occurs at 3.78 K.')]
    def snapshot(*args):
        current = draft['material_states'][0]['property_modules'][0]['records'][0]
        rows = [dict(key='tc', field='material_states[0].property_modules[0].records[0]', kind='property',
                     state_index=0, module_key='module-tc', record_key='tc',
                     claim=record_claim(current, draft['material_states'][0]), evidences=current.get('evidences', []))]
        return ev.complete_snapshot('upload', 'task', rows, chunks, draft)
    job = dict(owner=2, status='completed', snapshot=snapshot(), results={'tc': {
        'status': 'supported', 'evidences': [{'file_id': 'main', 'quote': chunks[0]['content']}],
    }})
    original = job['snapshot']['version']
    if changed:
        record.update(value_number=4.2, value_raw='4.2')
    before = copy.deepcopy(draft)
    monkeypatch.setattr(ev, 'read_job', lambda *args: job)
    monkeypatch.setattr(ev, 'upload_snapshot', snapshot)
    monkeypatch.setattr(upload_tasks, 'upload_task_lock', lambda _: nullcontext())
    monkeypatch.setattr(upload_tasks, 'get_draft', lambda _: copy.deepcopy(draft))
    writes = []
    def save(_, value):
        writes.append(copy.deepcopy(value))
        draft.update(copy.deepcopy(value))
    monkeypatch.setattr(upload_tasks, 'save_draft', save)
    persisted_keys = []
    monkeypatch.setattr(upload_tasks, 'redis_client', lambda: SimpleNamespace(persist=persisted_keys.append))
    result = api.save_upload_evidence_draft('job', SimpleNamespace(id=2))
    assert result == {'status': 'saved', 'version': original}
    assert len(writes) == 1
    if changed:
        assert writes[0] == before
        assert snapshot()['version'] != original
        assert not persisted_keys
    else:
        saved = draft['material_states'][0]['property_modules'][0]['records'][0]
        assert saved['evidences'][0]['quote'] == chunks[0]['content']
        assert saved['value_number'] == 3.78
        assert snapshot()['version'] == original
        assert persisted_keys == [upload_tasks.task_key('task'), upload_tasks.draft_key('task')]

"""#137/#185：入队版本取持久工作稿，不能把JSON存储差异当成编辑。"""
from copy import deepcopy
import os
from types import SimpleNamespace
from uuid import uuid4

import pytest
from backend import models
from backend.ingest import upload_tasks
from backend.services import spectra, workdrafts
from backend.ingest.tc_contexts import map_draft
from test_scientific_evidence_mysql import current_mysql

pytestmark = pytest.mark.skipif(os.environ.get('SCWIKI_CURRENT_MYSQL') != '1', reason='仅显式启用本机回滚测试')


def test_first_spectrum_enqueue_uses_persisted_workdraft_version(current_mysql, monkeypatch):
    task = uuid4().hex
    actor = SimpleNamespace(id=2, role='user', username='isolated-owner')
    state = {'task_id': task, 'user_id': 2, 'status': 'ready', 'files': []}
    draft = {'_field_edit_format': 1, 'paper': {'title': 'H'}, 'material_states': [{
        'state_key': 'h', 'material': 'H', 'evidences': [{'bbox': [442.32268524169916, 1, 2, 3]}],
        'structure': {'validation': {'cell_parameters': {'a': 3.5009999999999994}}}, 'property_modules': []}]}
    monkeypatch.setattr(upload_tasks, 'get_state', lambda _: state)
    monkeypatch.setattr(upload_tasks, 'authoritative_state', lambda *a: state)
    def get_draft(_):
        with current_mysql() as db:
            saved = workdrafts.row(db, 'upload', task)
            return map_draft(deepcopy(saved.body)) if saved else deepcopy(draft)
    monkeypatch.setattr(upload_tasks, 'get_draft', get_draft)
    with current_mysql.begin() as db:
        first = spectra.context(db, 'upload', task, actor, write=True)
    with current_mysql.begin() as db:
        reopened = spectra.context(db, 'upload', task, actor, write=True)
    assert first['version'] == reopened['version']
    assert first['states'] == reopened['states']
    with current_mysql.begin() as db:
        saved = workdrafts.row(db, 'upload', task)
        changed = deepcopy(saved.body)
        changed['material_states'][0]['pressure_value_gpa'] = 150
        saved.body = changed
    with current_mysql() as db:
        assert spectra.context(db, 'upload', task, actor)['version'] != first['version']

"""文件身份错误首行重放、正式入口及确认版本。"""
import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from backend.ingest.document_identity import extract_identity, compare_identities, confirmation

TITLE = 'Predicted hot superconductivity in LaSc2H24 under pressure'
FOOTER = 'PNAS 2024 Vol. 121 No. 26 e2401840121 https://doi.org/10.1073/pnas.2401840121 1 of 6'
MAIN = f'<!-- page: 1 -->\n{FOOTER}\nRESEARCH ARTICLE\n## {TITLE}\nXin-Ling He, Wenbo Zhao\n## Abstract\nScientific content.\n'
SI = f'<!-- page: 1 -->\n1\n## SUPPLEMENTARY INFORMATION\n{TITLE}\nXin-Ling He, Wenbo Zhao\n'


def identities(main=MAIN, si=SI):
    return [extract_identity({'file_id': 'si', 'role': 'supplementary', 'original_filename': 'SI.pdf'}, si),
            extract_identity({'file_id': 'main', 'role': 'main', 'original_filename': 'paper.pdf'}, main)]


def test_original_failure_replay_and_formal_worker_entry(monkeypatch):
    from backend.ingest import upload_jobs, upload_contracts
    monkeypatch.setattr(upload_jobs, 'complete_json', lambda *a, **k: pytest.fail('文件身份检查不能调用模型'))
    legacy = compare_identities([{'file_id': 'si', 'role': 'main', 'title': '1'},
                                {'file_id': 'main', 'role': 'attachment', 'title': FOOTER}])
    assert legacy['status'] == 'warning'
    items = [upload_jobs._lightweight_identity({'file_id': 'si', 'role': 'main'}, SI),
             upload_jobs._lightweight_identity({'file_id': 'main', 'role': 'attachment'}, MAIN)]
    from backend.ingest.document_roles import assess_roles
    roles = assess_roles([{'file_id': 'si', 'role': 'main', 'kind': 'pdf', 'original_filename': 'paper-SI.pdf'},
                          {'file_id': 'main', 'role': 'attachment', 'kind': 'pdf', 'original_filename': 'paper.pdf'}],
                         {'si': SI, 'main': MAIN + '\n## Introduction\n'})
    for item in items:
        item['role'] = next(f['effective_role'] for f in roles['files'] if f['file_id'] == item['file_id'])
    checked = upload_contracts.compare_file_identities(items)
    assert checked['status'] == 'ok' and not checked['conflicts']
    assert {item['title'] for item in items} == {TITLE}
    assert items[1]['doi'] == '10.1073/pnas.2401840121'


@pytest.mark.parametrize('text', ['1\nSupplementary Information\n', 'PNAS 2024 Vol. 121 No. 26 1 of 6\n',
    '## Methods\nWe describe calculations here.\n', '## References\nhttps://doi.org/10.1000/cited\n'])
def test_noise_is_unknown(text):
    item = extract_identity({'file_id': 'x'}, text)
    assert item['title'] is None and item['doi'] is None


def test_reference_doi_and_pnas_link_in_prose_are_not_own_doi():
    text = MAIN + 'This article contains supporting information at https://www.pnas.org/lookup/doi:10.1073/other\n'
    text += '## References\nhttps://doi.org/10.1000/cited\n'
    assert extract_identity({}, text)['doi'] == '10.1073/pnas.2401840121'


def test_unlabelled_reference_and_numbered_section_do_not_become_identity():
    text = '## S1. Electronic structure of the material\nWe calculate bands, using DFT.\nPNAS 2019 Vol. 116 No. 1 https://doi.org/10.1000/cited\n'
    item = extract_identity({}, text)
    assert item['title'] is None and item['doi'] is None


def test_wrapped_and_typeset_title_preserves_chemical_identity():
    wrapped = MAIN.replace(TITLE, 'Predicted hot superconductivity in LaSc₂H₂₄\nunder pressure')
    assert compare_identities(identities(wrapped))['status'] == 'ok'
    assert compare_identities(identities(MAIN.replace('H24', 'H30')))['status'] == 'warning'


def test_real_doi_conflict_has_actual_files_and_fields():
    result = compare_identities(identities(si=SI + '\ndoi:10.1000/other\n'))
    assert [c['field'] for c in result['conflicts']] == ['doi']
    assert result['conflicts'][0]['main_filename'] == 'paper.pdf'
    assert result['conflicts'][0]['filename'] == 'SI.pdf'
    message, token = confirmation({'consistency': result, 'files': []})
    assert 'DOI' in message and '10.1000/other' in message and '作者' not in message and '标题' not in message
    assert len(token) == 64


def test_single_file_and_missing_values_do_not_claim_match():
    assert compare_identities(identities()[:1])['status'] == 'unknown'
    assert compare_identities(identities(si='1\nSupporting information\n'))['status'] == 'unknown'


def test_submit_confirmation_uses_exact_current_file_version(monkeypatch):
    from backend.api import rag
    from backend.ingest import property_evidence, upload_tasks
    state = {'user_id': 7, 'stage': 'ready', 'processing_status': 'succeeded',
        'files': [{'file_id': 'main', 'role': 'main', 'sha256': 'first'}],
        'consistency': compare_identities(identities(si=SI + '\ndoi:10.1000/other'))}
    async def absent(_): return None
    monkeypatch.setattr(rag, '_submitted_paper_for_task', absent)
    monkeypatch.setattr(rag, '_task_for_user', lambda *a: state)
    monkeypatch.setattr(upload_tasks, 'get_draft', lambda _: {'paper': {}})
    class ReachedFieldGate(Exception): pass
    def next_gate(*a): raise ReachedFieldGate()
    monkeypatch.setattr(property_evidence, 'upload_snapshot', next_gate)
    actor = SimpleNamespace(id=7)
    with pytest.raises(HTTPException) as failure:
        asyncio.run(rag._submit_upload_draft_locked('task', actor))
    assert failure.value.detail['code'] == 'consistency_ack_required'
    token = failure.value.detail['consistency_version']
    assert 'SI.pdf' in failure.value.detail['message'] and '标题' not in failure.value.detail['message']
    with pytest.raises(ReachedFieldGate):
        asyncio.run(rag._submit_upload_draft_locked('task', actor, consistency_acknowledged=True, consistency_version=token))
    state['files'][0]['sha256'] = 'changed'
    with pytest.raises(HTTPException) as stale:
        asyncio.run(rag._submit_upload_draft_locked('task', actor, consistency_acknowledged=True, consistency_version=token))
    assert stale.value.detail['consistency_version'] != token

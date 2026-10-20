"""完整规则结果在真实MySQL重读；所有测试写入由外层事务回滚。"""
import os
import uuid
from copy import deepcopy
import pytest

from backend.ingest import property_evidence as ev, scientific_evidence as science
from test_scientific_evidence_mysql import current_mysql
from test_condition_auto_review import snapshot, evaluate

pytestmark=pytest.mark.skipif(os.environ.get('SCWIKI_CURRENT_MYSQL')!='1',reason='需要显式启用事务回滚MySQL')


@pytest.mark.parametrize('target',['upload','revision','paper'])
def test_rule_survives_reload_and_old_rule_cannot_approve(current_mysql,monkeypatch,target):
    snap,row=snapshot(target=target);snap['target_id']=str(uuid.uuid4().int % 1000000000 + 1000000000) if target=='paper' else uuid.uuid4().hex
    _,results=evaluate(monkeypatch,snap,row)
    with current_mysql.begin() as db:science.save_results(db,{**snap,'records':[row]},results,7)
    with current_mysql.begin() as db:
        loaded=science.load_results(db,{**snap,'records':[row]},7)
        current=ev.checked_result(row,loaded[row['key']],snap['chunks'])
        assert current['status']=='supported' and current['adopted_basis']=='paper_inference'
        assert not current['human_confirmed'] and not current['decision']
        assert ev.resolve_results({**snap,'records':[row]},loaded,7,None,snap['version'])[0]['status']=='supported'
        old=deepcopy(loaded[row['key']]);old['rule_review']['version']='obsolete'
        assert ev.checked_result(row,old,snap['chunks'])['status']!='supported'


def test_late_older_review_cannot_replace_newer_result_but_new_conflict_can(current_mysql,monkeypatch):
    snap,row=snapshot();snap['target_id']=uuid.uuid4().hex
    _,newer=evaluate(monkeypatch,snap,row)
    newer[row['key']]['review_started_at']='2026-10-20T10:10:00+00:00'
    with current_mysql.begin() as db:science.save_results(db,{**snap,'records':[row]},newer,7)
    old=deepcopy(newer)
    old[row['key']].update(review_started_at='2026-10-20T10:00:00+00:00',status='uncertain',rule_review=None,reason='迟到的旧核对')
    with current_mysql.begin() as db:science.save_results(db,{**snap,'records':[row]},old,7)
    assert old[row['key']]['rule_review'] and old[row['key']]['superseded_review']['reason']=='迟到的旧核对'
    with current_mysql.begin() as db:
        cached=science.load_results(db,{**snap,'records':[row]},7)
        assert ev.checked_result(row,cached[row['key']],snap['chunks'])['status']=='supported'
    conflict=deepcopy(newer)
    conflict[row['key']].update(review_started_at='2026-10-20T10:20:00+00:00',status='unsupported',rule_review=None,
                               association_conflict=True,reason='新的完整核对发现范围冲突')
    with current_mysql.begin() as db:science.save_results(db,{**snap,'records':[row]},conflict,7)
    with current_mysql.begin() as db:
        cached=science.load_results(db,{**snap,'records':[row]},7)
        assert ev.checked_result(row,cached[row['key']],snap['chunks'])['status']=='unsupported'

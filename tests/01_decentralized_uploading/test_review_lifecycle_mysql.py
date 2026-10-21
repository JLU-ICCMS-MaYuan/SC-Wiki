"""真实MySQL事务回滚验证；不写用户草稿，不调用模型。"""
import os
import uuid
import json
from pathlib import Path
from copy import deepcopy
import pytest
from backend.ingest import property_evidence as ev, scientific_evidence as science, evidence_proposals as proposals
from test_scientific_evidence_mysql import current_mysql
from test_review_lifecycle import legacy_review

pytestmark = pytest.mark.skipif(os.environ.get('SCWIKI_CURRENT_MYSQL') != '1', reason='需要显式启用MySQL回滚')


def source_snapshot():
    # 固定生产快照可隔离同期来源解析改动，验证本次保存/重验合同；不伪称覆盖来源读取。
    if os.environ.get('SCWIKI_SOURCE_SNAPSHOT'):
        return json.loads(Path(os.environ['SCWIKI_SOURCE_SNAPSHOT']).read_text())
    return ev.upload_snapshot(os.environ['SCWIKI_SOURCE_TASK'],2)


def test_legacy_then_failed_attempt_then_conflict_reload(current_mysql, monkeypatch):
    snap,row,old=legacy_review(monkeypatch)
    snap={**snap,'target_id':uuid.uuid4().hex,'records':[row]}
    old_snapshot={**snap,'records':[{**row,'claim':old['claim'],'content_hash':old['content_hash']}]}
    with current_mysql.begin() as db: science.save_results(db,old_snapshot,{row['key']:old},7)
    failed={**deepcopy(row),'status':'uncertain','reason':'软件段落遗漏','rule_review':None}
    with current_mysql.begin() as db: science.save_results(db,snap,{row['key']:failed},7)
    with current_mysql.begin() as db:
        loaded=science.load_results(db,snap,7)[row['key']]
        assert ev.checked_result(row,loaded,snap['chunks'])['status']=='supported'
        assert loaded['review_attempt']['reason']=='软件段落遗漏'
    conflict={**failed,'condition_conflict':True}
    with current_mysql.begin() as db:science.save_results(db,snap,{row['key']:conflict},7)
    with current_mysql.begin() as db:
        assert ev.checked_result(row,science.load_results(db,snap,7)[row['key']],snap['chunks'])['status']!='supported'


@pytest.mark.parametrize('target',['upload','revision','paper'])
@pytest.mark.skipif(not (os.environ.get('SCWIKI_SOURCE_TASK') or os.environ.get('SCWIKI_SOURCE_SNAPSHOT')), reason='需显式指定真实草稿副本来源')
def test_real_sscha_accept_and_finalize_keep_rule_identity(current_mysql,target):
    original=source_snapshot()
    row=next(r for r in original['records'] if r.get('record_field_key')=='sscha.calculation_code'
             and r['claim']['context'].get('pressure_value_gpa')==200)
    with current_mysql.begin() as db: prior=science.load_results(db,original,2)[row['key']]
    snap={**original,'target':target,'target_id':str(uuid.uuid4().int % 1000000000+1000000000),'records':[row]}
    with current_mysql.begin() as db:science.save_results(db,snap,{row['key']:prior},2)
    with current_mysql.begin() as db:
        draft=proposals.save_draft(db,snap,2,row['key'],{'':row['current_value']},True,'')
        assert draft['supported'] and not draft['human_confirmed']
        assert draft['basis_kind']=='paper_inference'
    with current_mysql.begin() as db:
        prepared=proposals.prepare(db,snap,2)
        assert prepared['patches']
        proposals.finalize(db,snap,2,prepared['preparation_id'])
    with current_mysql.begin() as db:
        read=ev.checked_result(row,science.load_results(db,snap,2)[row['key']],snap['chunks'])
        assert read['status']=='supported' and read['rule_review']
        assert not read['human_confirmed'] and read['adopted_basis']=='paper_inference'


@pytest.mark.skipif(not (os.environ.get('SCWIKI_SOURCE_TASK') or os.environ.get('SCWIKI_SOURCE_SNAPSHOT')), reason='需显式指定真实草稿副本来源')
def test_real_dos_name_draft_saves_without_accepting_science(current_mysql):
    original=source_snapshot()
    row=next(r for r in original['records'] if r.get('claim',{}).get('record',{}).get('property_code')=='dos_fermi'
             and r['claim']['record'].get('value_raw')=='17.27')
    snap={**original,'target_id':uuid.uuid4().hex,'records':[row]}
    values={f['path']:f['value'] for f in proposals.editable_fields(row)}
    values['name_raw']='N(EF)'
    with current_mysql.begin() as db:
        draft=proposals.save_draft(db,snap,2,row['key'],values,False,'')
        assert not draft['accepted'] and not draft['human_confirmed']
    with current_mysql.begin() as db:
        result=science.load_results(db,snap,2)[row['key']]
        assert result['proposal_draft']['values']['name_raw']=='N(EF)'
        assert result['proposal_draft']['values']['value_number'] is None


def test_same_version_failure_cannot_erase_only_valid_proof(current_mysql,monkeypatch):
    from test_condition_auto_review import snapshot,evaluate
    snap,row=snapshot();snap={**snap,'target_id':uuid.uuid4().hex,'records':[row]}
    _,results=evaluate(monkeypatch,snap,row)
    with current_mysql.begin() as db:science.save_results(db,snap,results,7)
    with current_mysql.begin() as db:
        science.save_results(db,snap,{row['key']:{'status':'uncertain','reason':'本次漏引',
            'rule_review':None,'condition_window_errors':['软件证据遗漏']}},7)
    with current_mysql.begin() as db:
        loaded=science.load_results(db,snap,7)[row['key']]
        assert loaded['review_attempt']['reason']=='本次漏引'
        assert ev.checked_result(row,loaded,snap['chunks'])['status']=='supported'

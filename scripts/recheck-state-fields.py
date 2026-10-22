"""#149 定向查证已填状态字段；默认盘点，--apply 才调用模型并保存核对结果。"""
from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str))
    path.chmod(0o600)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--task-id', required=True)
    parser.add_argument('--state-key', required=True)
    parser.add_argument('--owner', type=int, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--creation-before', type=Path)
    parser.add_argument('--creation-after', type=Path)
    args = parser.parse_args()
    from dotenv import load_dotenv
    load_dotenv(ROOT / '.env')
    from sqlalchemy import select
    from backend import models
    from backend.database import SessionLocal
    from backend.ingest import property_evidence as ev, scientific_evidence as science, field_review
    from backend.ingest.upload_tasks import redis_client, upload_task_lock, task_key, draft_key
    from backend.ingest.pdf_source_pages import current_pdf_results
    from backend.rag.llm_context import get_llm_config

    os.umask(0o077)
    args.output.mkdir(parents=True, exist_ok=False)
    client = redis_client()
    raw_draft, raw_state = client.get(draft_key(args.task_id)), client.get(task_key(args.task_id))
    if not raw_draft or not raw_state:
        raise ValueError('目标草稿不存在，不恢复或创建新草稿')
    original_draft, original_state = json.loads(raw_draft), json.loads(raw_state)
    snapshot = ev.upload_snapshot(args.task_id, args.owner)
    if not snapshot['chunks'] or snapshot.get('condition_source_manifest_complete') is False:
        raise ValueError('来源未完整读取，不能查证')
    with SessionLocal() as session:
        cached = science.load_results(session, snapshot, args.owner, include_stale=True)
        rows = session.execute(select(models.ScientificEvidenceCheck).where(
            models.ScientificEvidenceCheck.target == 'upload',
            models.ScientificEvidenceCheck.target_id == args.task_id)).scalars().all()
        checks = [{c.name: getattr(row,c.name) for c in row.__table__.columns} for row in rows]
        saved = session.get(models.ScientificUploadDraft,args.task_id)
        durable_before = {'draft':deepcopy(saved.draft),'state':deepcopy(saved.state)} if saved else None
    selected = [r for r in snapshot['records'] if r.get('state_key') == args.state_key
                and r.get('kind') == 'field' and not r.get('module_key')
                and science.populated(r.get('current_value'))
                and not (field_review.reusable(r,cached.get(r['key'])) and cached[r['key']]['status']=='supported')]
    write(args.output/'before-draft.json',original_draft)
    write(args.output/'before-state.json',original_state)
    write(args.output/'before-checks.json',checks)
    write(args.output/'before-durable.json',durable_before)
    write(args.output/'selected.json',selected)
    write(args.output/'sources.json',snapshot['chunks'])
    print(json.dumps({'selected':[r['field'] for r in selected],'apply':args.apply},ensure_ascii=False),flush=True)
    if not args.apply or not selected:
        return

    proof = None
    if args.creation_before and args.creation_after:
        before = json.loads(args.creation_before.read_text())
        after = json.loads(args.creation_after.read_text())
        assert not any(s.get('state_key') == args.state_key for s in before['material_states'])
        new_state = next(s for s in after['material_states'] if s.get('state_key') == args.state_key)
        old_records = {r['item_key']:r for r in science.state_records(new_state,0)}
        events = [e for e in original_state.get('_field_change_events',[]) if e.get('item_key') in old_records
                  and e.get('summary')=='新增字段' and e.get('before_value') is None
                  and science.canonical(e.get('after_value'))==science.canonical(old_records[e['item_key']]['current_value'])]
        assert events, '历史创建事件无法由备份确认'
        proof = {'id':uuid4().hex,'kind':'state_creation_provenance','state_key':args.state_key,
                 'value_origin':'system_assembly','source_issue':149,
                 'summary':'按历史独立备份补充系统按原文拆分状态的来源说明，原事件保留',
                 'creation_event_ids':[e['id'] for e in events],
                 'backup_sha256':hashlib.sha256(args.creation_before.read_bytes()).hexdigest(),
                 'after_backup_sha256':hashlib.sha256(args.creation_after.read_bytes()).hexdigest(),
                 'occurred_at':datetime.now(timezone.utc).isoformat()}
        write(args.output/'creation-provenance.json',proof)

    run_id=uuid4().hex
    locks=['field-review-job:'+ev.digest(['upload',args.task_id,r['item_key'],r['content_hash'],r['source_hash']]) for r in selected]
    conflict=client.eval("for _,k in ipairs(KEYS) do if redis.call('exists',k)==1 then return 1 end end for _,k in ipairs(KEYS) do redis.call('set',k,ARGV[1],'EX',1800) end return 0",len(locks),*locks,run_id)
    if conflict:
        raise ValueError('目标字段已有核对任务；没有覆盖或重复执行')
    try:
        config=get_llm_config()
        if not config.api_key:
            raise ValueError('未配置模型')
        started=datetime.now(timezone.utc).isoformat()
        candidates={r['key']:[] for r in selected}
        errors={r['key']:[] for r in selected}
        batches=ev.source_batches(snapshot['chunks'])
        write(args.output/'call-metadata.json',{'model':config.model,'review_started_at':started,'batches':len(batches)})
        for i,chunks in enumerate(batches):
            print(json.dumps({'reviewing_batch':i+1,'total_batches':len(batches),'fields':len(selected)}),flush=True)
            evaluated=ev.evaluate_batch(selected,chunks,purpose='field',prior=cached,
                source_catalog=snapshot['chunks'],review_started_at=started,
                on_response=lambda raw,index=i:write(args.output/f'model-response-{index}.json',raw))
            write(args.output/f'evaluated-{i}.json',evaluated)
            for record,result in zip(selected,evaluated):
                candidates[record['key']].append(result)
                errors[record['key']].extend(result.get('location_errors') or [])
        results=ev.aggregate_candidates(selected,candidates,errors,config.model,snapshot['chunks'])
        for result in results.values():
            result['proposal']=None  # 查证，不采纳/填充任何科学值。
            result['human_confirmed']=False
        with SessionLocal() as session:
            results=current_pdf_results(session,{**snapshot,'records':selected},results)
        write(args.output/'review-results.json',results)
        with upload_task_lock(args.task_id):
            if client.get(draft_key(args.task_id)) != raw_draft:
                raise ValueError('用户已编辑草稿，本次结果未应用')
            current=ev.upload_snapshot(args.task_id,args.owner)
            if current['version'] != snapshot['version']:
                raise ValueError('内容、依据或状态条件已变，本次结果未应用')
            state_now=json.loads(client.get(task_key(args.task_id)))
            if state_now.get('_field_change_events') != original_state.get('_field_change_events'):
                raise ValueError('字段审计记录已变，来源说明未应用')
            if proof:
                state_now['_field_change_events']=[*state_now.get('_field_change_events',[]),proof]
            with SessionLocal.begin() as session:
                stored=session.get(models.ScientificUploadDraft,args.task_id,with_for_update=True)
                if not stored or science.canonical(stored.draft)!=science.canonical(durable_before['draft']):
                    raise ValueError('持久草稿已变，停止写入')
                field_review.validate_support_versions({**snapshot,'records':selected},session)
                science.save_results(session,{**snapshot,'records':selected},results,args.owner)
                if proof:
                    stored.state=state_now
            if proof:
                client.set(task_key(args.task_id),json.dumps(state_now,ensure_ascii=False),keepttl=True)
        assert client.get(draft_key(args.task_id))==raw_draft,'草稿意外变化'
        with SessionLocal() as session:
            after=ev.upload_snapshot(args.task_id,args.owner)
            stored=science.load_results(session,after,args.owner,include_stale=True)
            selected_keys={r['item_key'] for r in selected}
            preserved={row['id']:ev.digest({k:row[k] for k in ('result','resolutions')}) for row in checks if row['item_key'] not in selected_keys}
            for row in session.scalars(select(models.ScientificEvidenceCheck).where(models.ScientificEvidenceCheck.id.in_(preserved))):
                assert ev.digest({'result':row.result,'resolutions':row.resolutions})==preserved[row.id]
            durable=session.get(models.ScientificUploadDraft,args.task_id)
            assert science.canonical(durable.draft)==science.canonical(durable_before['draft'])
        from backend.ingest.field_decisions import detail
        report=[]
        for row in after['records']:
            if row['item_key'] not in selected_keys:continue
            view=detail({**after,'records':[row]},stored)
            report.append({'field':row['field'],'status':view['record']['status'],
                           'evidences':len(view['record']['evidences']),'can_approve':view['can_approve'],
                           'human_confirmed':view['record']['human_confirmed'],
                           'reason':view['record']['reason']})
        final={'fields':report,'scientific_values_unchanged':True,'unselected_checks_unchanged':len(preserved),
               'new_manual_approvals':0,'source_provenance_appended':bool(proof),'backup':str(args.output)}
        write(args.output/'verification.json',final)
        print(json.dumps(final,ensure_ascii=False),flush=True)
    finally:
        client.eval("for _,k in ipairs(KEYS) do if redis.call('get',k)==ARGV[1] then redis.call('del',k) end end return 1",len(locks),*locks,run_id)


if __name__=='__main__':
    main()

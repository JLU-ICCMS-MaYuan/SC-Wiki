"""显式论文范围的共享资料备份、隔离演练和无损精简；默认只读。"""
from __future__ import annotations
import argparse
from copy import deepcopy
from datetime import datetime
import gzip
import hashlib
import json
from pathlib import Path
import sys
from urllib.parse import urlparse
import uuid
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
Q=chr(96)


def encode(value):
    return json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':'),default=str)


def digest(value):
    return hashlib.sha256(encode(value).encode()).hexdigest()


def table_map():
    from backend.database import Base
    from backend import models,manual_evidence_models
    return {t.name:t for t in Base.metadata.sorted_tables}


def identity(db,paper_id,expected):
    from backend import models as m
    from sqlalchemy import select
    p=db.get(m.Paper,paper_id)
    f=db.scalar(select(m.PaperFile).where(m.PaperFile.paper_id==paper_id,m.PaperFile.role=='main'))
    if p is None or f is None or f.sha256!=expected:raise ValueError('目标论文或正文SHA不匹配')
    revisions=list(db.scalars(select(m.PaperRevisionDraft.revision_id).where(m.PaperRevisionDraft.paper_id==paper_id)))
    return {'paper_id':paper_id,'title':p.title,'main_sha256':f.sha256,'task_id':p.upload_task_id,
        'paper_revision':p.content_revision,'targets':[['paper',str(paper_id)],*[['revision',x] for x in revisions],
        *([['upload',p.upload_task_id]] if p.upload_task_id else [])]}


def collect(db,scope):
    from sqlalchemy import select,or_,and_,inspect
    existing=set(inspect(db.connection()).get_table_names())
    lookup={n:t for n,t in table_map().items() if n in existing};output={}
    for name,t in lookup.items():
        clauses=[]
        if name=='papers':clauses.append(t.c.id==scope['paper_id'])
        if 'paper_id' in t.c:clauses.append(t.c.paper_id==scope['paper_id'])
        if 'target' in t.c and 'target_id' in t.c:
            clauses.extend(and_(t.c.target==a,t.c.target_id==b) for a,b in scope['targets'])
        if name=='scientific_upload_drafts':clauses.append(t.c.task_id==scope['task_id'])
        if name=='scientific_field_source_uses':clauses.append(t.c.work_key.in_([a+':'+b for a,b in scope['targets']]))
        if clauses:output[name]=[dict(r) for r in db.execute(select(t).where(or_(*clauses))).mappings()]
    refs=set()
    def scan(v):
        if isinstance(v,dict):
            for k,x in v.items():
                if k in {'source_ref','shared_context_ref'} and isinstance(x,str):refs.add(x)
                else:scan(x)
        elif isinstance(v,list):
            for x in v:scan(x)
    scan(output)
    for r in output.get('scientific_field_source_uses',[]):refs.add(r['source_id'])
    sources={};t=lookup['scientific_source_items']
    while refs-set(sources):
        needed=refs-set(sources)
        rows=[dict(r) for r in db.execute(select(t).where(t.c.id.in_(needed))).mappings()]
        if {r['id'] for r in rows}!=needed:raise ValueError('旧资料引用已缺失')
        for r in rows:sources[r['id']]=r;scan(r['payload'])
    output[t.name]=list(sources.values())
    return {n:sorted(rows,key=lambda r:encode([r.get(c.name) for c in lookup[n].primary_key.columns]))
        for n,rows in sorted(output.items()) if rows}


def logical(db,scope):
    from backend.ingest.field_sources import expand
    from sqlalchemy.sql.sqltypes import JSON
    rows=collect(db,scope);lookup=table_map()
    for name,entries in rows.items():
        for row in entries:
            for c in lookup[name].c:
                if isinstance(c.type,JSON) and row.get(c.name) is not None:row[c.name]=expand(db,row[c.name])
    rows.pop('scientific_source_items',None)
    return json.loads(encode(rows))


def sizes(db,scope):
    from sqlalchemy import select,func,tuple_
    from sqlalchemy.sql.sqltypes import JSON
    output={}
    for name,rows in collect(db,scope).items():
        t=table_map()[name];pk=list(t.primary_key.columns)
        where=tuple_(*pk).in_([tuple(r[k.name] for k in pk) for r in rows])
        expressions=[func.coalesce(func.json_storage_size(c),0) for c in t.c if isinstance(c.type,JSON)]
        binary=int(db.scalar(select(func.coalesce(func.sum(sum(expressions)),0)).where(where)) or 0) if expressions else 0
        text=sum(len(v.encode()) for r in rows for k,v in r.items() if isinstance(v,str))
        output[name]={'rows':len(rows),'content_bytes':binary+text}
    return output


def json_path(path):
    return '$'+''.join('['+str(k)+']' if isinstance(k,int) else '.'+json.dumps(k,ensure_ascii=False) for k in path)


def float_paths(v,path=()):
    if isinstance(v,dict):
        for k,x in v.items():yield from float_paths(x,(*path,k))
    elif isinstance(v,list):
        for k,x in enumerate(v):yield from float_paths(x,(*path,k))
    elif isinstance(v,float):yield path,v


def restore(conn,rows):
    from sqlalchemy import text,select,and_
    from sqlalchemy.sql.sqltypes import JSON,DateTime
    lookup=table_map()
    conn.exec_driver_sql('SET FOREIGN_KEY_CHECKS=0')
    try:
        for name,entries in rows.items():
            t=lookup[name];conn.execute(t.delete())
            for r in entries:
                values={c.name:(datetime.fromisoformat(r[c.name]) if isinstance(c.type,DateTime) and r.get(c.name) is not None
                    else r.get(c.name)) for c in t.c if c.computed is None}
                conn.execute(t.insert().values(**values))
                where=' AND '.join(Q+c.name+Q+'=:pk_'+c.name for c in t.primary_key.columns)
                params={'pk_'+c.name:r[c.name] for c in t.primary_key.columns}
                for c in t.c:
                    if isinstance(c.type,JSON) and r.get(c.name) is not None:
                        actual=conn.scalar(select(c).where(and_(*[k==r[k.name] for k in t.primary_key.columns])))
                        for path,number in float_paths(r[c.name]):
                            found=actual
                            for key in path:found=found[key]
                            if isinstance(found,float) and found.hex()==number.hex():continue
                            conn.execute(text('UPDATE '+Q+name+Q+' SET '+Q+c.name+Q+'=JSON_SET('+Q+c.name+Q+
                                ',:path,CAST(:number AS DOUBLE)) WHERE '+where),
                                {**params,'path':json_path(path),'number':repr(number)})
    finally:conn.exec_driver_sql('SET FOREIGN_KEY_CHECKS=1')


def compact(db,scope,artifact_verified):
    from sqlalchemy import select,text,or_,and_
    from backend import models as m
    from backend.ingest.field_sources import compact_contexts,expand,CONTEXT_CONTRACT
    from backend.workdraft_models import ScientificSourceItem,ScientificWorkDraft
    targets=[(m.ScientificEvidenceSource,'result',m.ScientificEvidenceSource.paper_id==scope['paper_id'],False),
        (m.PaperHistoryEvent,'classification_snapshot',m.PaperHistoryEvent.paper_id==scope['paper_id'],True),
        (m.ScientificEvidenceCheck,'result',or_(*[and_(m.ScientificEvidenceCheck.target==a,
            m.ScientificEvidenceCheck.target_id==b) for a,b in scope['targets']]),False)]
    report={'changes':[],'new_context_ids':[]}
    for cls,col,where,structure_sources in targets:
        for row_id in sorted(db.scalars(select(cls.id).where(where))):
            row=db.get(cls,row_id,with_for_update=True)
            old=deepcopy(getattr(row,col));expanded=expand(db,old);replacements=[]
            def store(key,value,path):
                existing=db.get(ScientificSourceItem,key)
                if existing is None:
                    # 数据库原生JSON复制保留DOUBLE，绝不以重新解析文本替代。
                    db.execute(text('INSERT INTO scientific_source_items (id,namespace,payload) SELECT '
                        ":key,:contract,JSON_OBJECT('contract',:contract,'value',JSON_EXTRACT("+Q+col+Q+
                        ',:path)) FROM '+Q+cls.__tablename__+Q+' WHERE id=:id'),
                        {'key':key,'contract':CONTEXT_CONTRACT,'path':json_path(path),'id':row_id})
                    report['new_context_ids'].append(key)
                elif existing.payload.get('contract')!=CONTEXT_CONTRACT or existing.payload.get('value')!=value:
                    raise ValueError('共享资料内容身份冲突')
                replacements.append((path,{'shared_context_ref':key}))
            keys={'legacy_evidences','legacy_source_history'}|({'sources'} if structure_sources else set())
            compact_contexts(db,old,keys=keys,store=store)
            if not replacements:continue
            expression=Q+col+Q;params={'id':row_id}
            for i,(path,ref) in enumerate(replacements):
                expression='JSON_SET('+expression+',:path'+str(i)+',CAST(:ref'+str(i)+' AS JSON))'
                params['path'+str(i)]=json_path(path);params['ref'+str(i)]=encode(ref)
            db.execute(text('UPDATE '+Q+cls.__tablename__+Q+' SET '+Q+col+Q+"=JSON_EXTRACT("+expression+", '$') WHERE id=:id"),params)
            db.expire(row,[col])
            if expand(db,getattr(row,col))!=expanded:raise ValueError('逻辑内容或科学浮点改变，回滚')
            report['changes'].append({'table':cls.__tablename__,'id':row_id,'contexts':len(replacements)})
    work=db.scalar(select(ScientificWorkDraft).where(ScientificWorkDraft.target=='upload',
        ScientificWorkDraft.target_id==scope['task_id']).with_for_update())
    if work is not None and work.body:
        if not artifact_verified or not work.document_key.startswith('closed:'):raise ValueError('旧上传稿尚未可靠交出')
        event=db.get(m.PaperHistoryEvent,int(work.document_key.split(':',1)[1]))
        if event is None or event.paper_id!=scope['paper_id'] or not event.classification_snapshot.get('manuscript_snapshot'):
            raise ValueError('关闭稿缺少正式完整快照')
        db.execute(text('UPDATE scientific_work_drafts SET body=JSON_OBJECT() WHERE id=:id'),{'id':work.id})
        db.expire(work,['body'])
        report['changes'].append({'table':'scientific_work_drafts','id':work.id,'closed_body':True})
    report['changed_rows']=len(report['changes'])
    db.flush()
    return report


def artifact(scope):
    from backend.ingest.upload_tasks import read_artifact_path,submitted_artifact_key
    from backend.storage import create_storage
    ref=create_storage().describe(submitted_artifact_key(scope['task_id'],scope['paper_id'],scope['paper_revision']))
    path=read_artifact_path(scope['task_id'],paper_id=scope['paper_id'],paper_revision=scope['paper_revision'])
    raw=path.read_bytes();v=json.loads(raw)
    if len(raw)!=ref.size or hashlib.sha256(raw).hexdigest()!=ref.sha256:raise ValueError('仓库产物校验失败')
    if (v.get('task_id'),v.get('paper_id'),v.get('paper_revision'))!=(scope['task_id'],scope['paper_id'],scope['paper_revision']):
        raise ValueError('仓库产物身份不匹配')
    return {'verified':True,'key':ref.key,'size':ref.size,'sha256':ref.sha256}


def compare_after(before,after):
    expected=deepcopy(before)
    for row in expected.get('scientific_work_drafts',[]):
        if row['target']=='upload' and row['document_key'].startswith('closed:'):row['body']={}
    if after!=expected:raise ValueError('展开内容、科学数值或非目标数据变化')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--mode',choices=['audit','backup','rehearse','apply'],default='audit')
    p.add_argument('--paper-id',type=int,required=True);p.add_argument('--expected-main-sha',required=True)
    p.add_argument('--backup',type=Path)
    a=p.parse_args()
    from scripts.local_deploy.config import read_config
    import os
    os.environ.update(read_config(ROOT))
    from backend.database import engine
    from sqlalchemy import create_engine,text,select
    from sqlalchemy.orm import Session
    from backend import models as m
    if engine.url.host not in {'127.0.0.1','localhost','::1'}:raise ValueError('只允许本轮已授权的本机数据库')
    if urlparse(os.environ.get('S3_ENDPOINT_URL','')).hostname not in {'127.0.0.1','localhost','::1'}:
        raise ValueError('只允许本机文件仓库')
    with Session(engine) as db:
        scope=identity(db,a.paper_id,a.expected_main_sha);rows=json.loads(encode(collect(db,scope)))
        before=logical(db,scope);report={'identity':scope,'sizes':sizes(db,scope),'plan_digest':digest(rows)}
    if a.mode=='audit':print(json.dumps(report,ensure_ascii=False,indent=2));return
    if a.backup is None:raise ValueError('必须指定私有备份目录')
    folder=a.backup
    if a.mode=='backup':
        folder.mkdir(parents=True,exist_ok=False,mode=0o700)
        with gzip.open(folder/'rows.json.gz','wt',encoding='utf8') as out:json.dump(rows,out,ensure_ascii=False)
        (folder/'rows.json.gz').chmod(0o600)
        report.update(backup_sha256=hashlib.sha256((folder/'rows.json.gz').read_bytes()).hexdigest(),
            logical_digest=digest(before),artifact=artifact(scope))
        (folder/'manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));(folder/'manifest.json').chmod(0o600)
        print(json.dumps({'backup':str(folder),'backup_bytes':(folder/'rows.json.gz').stat().st_size,
                         'plan_digest':report['plan_digest']},ensure_ascii=False));return
    meta=json.loads((folder/'manifest.json').read_text())
    if meta['identity']!=scope or meta['backup_sha256']!=hashlib.sha256((folder/'rows.json.gz').read_bytes()).hexdigest():
        raise ValueError('备份目标或摘要变化')
    with gzip.open(folder/'rows.json.gz','rt',encoding='utf8') as stream:backup=json.load(stream)
    if digest(backup)!=meta['plan_digest']:raise ValueError('备份内容摘要错误')
    if a.mode=='rehearse':
        name='scwiki_223_'+uuid.uuid4().hex[:12]
        from scripts.local_deploy.runtime import Runtime
        admin=create_engine('mysql+pymysql://',creator=Runtime(ROOT,Path(sys.executable).parent.parent,dict(os.environ)).mysql_inspection_connection,
                            isolation_level='AUTOCOMMIT')
        with admin.connect() as c:c.exec_driver_sql('CREATE DATABASE '+Q+name+Q+' CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci')
        isolated=create_engine(engine.url.set(database=name,username='root',password=os.environ['MYSQL_ROOT_PASSWORD']))
        try:
            with isolated.begin() as c:
                for table in backup:c.exec_driver_sql('CREATE TABLE '+Q+table+Q+' LIKE '+Q+engine.url.database+Q+'.'+Q+table+Q)
                restore(c,backup)
            with Session(isolated) as db:
                old=logical(db,scope)
                if digest(old)!=meta['logical_digest']:raise ValueError('隔离恢复与原始逻辑摘要不同')
                result=compact(db,scope,meta['artifact']['verified']);compare_after(old,logical(db,scope));db.commit()
            with Session(isolated) as db:
                result['idempotent']=compact(db,scope,True)['changed_rows']==0
                if not result['idempotent']:raise ValueError('重复精简不幂等')
                result['sizes_after']=sizes(db,scope);db.rollback()
            result.update(restored=True,logical_equal=True,plan_digest=meta['plan_digest'])
            (folder/'rehearsal.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
            print(json.dumps({k:v for k,v in result.items() if k not in {'changes','sizes_after'}},ensure_ascii=False))
        finally:
            isolated.dispose()
            with admin.connect() as c:c.exec_driver_sql('DROP DATABASE '+Q+name+Q)
            admin.dispose()
        return
    rehearsal=json.loads((folder/'rehearsal.json').read_text())
    if rehearsal.get('plan_digest')!=meta['plan_digest'] or not rehearsal.get('logical_equal'):
        raise ValueError('缺少对应备份的成功演练')
    stored=artifact(scope)
    with Session(engine) as db,db.begin():
        db.get(m.Paper,a.paper_id,with_for_update=True)
        db.execute(select(m.PaperRevisionDraft).where(m.PaperRevisionDraft.paper_id==a.paper_id).with_for_update())
        if digest(json.loads(encode(collect(db,scope))))!=meta['plan_digest']:raise ValueError('备份后有新修改，停止覆盖')
        old=logical(db,scope);result=compact(db,scope,stored['verified']);compare_after(old,logical(db,scope))
    from backend.ingest.artifact_retention import release_submitted_artifact
    result['local_cleanup']=release_submitted_artifact(scope['task_id'],scope['paper_id'],scope['paper_revision'])
    with Session(engine) as db:
        result['sizes_after']=sizes(db,scope);result['idempotent']=compact(db,scope,True)['changed_rows']==0;db.rollback()
    result.update(plan_digest=meta['plan_digest'],logical_equal=True,artifact=stored)
    (folder/'applied.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
    print(json.dumps({k:v for k,v in result.items() if k not in {'changes','sizes_after'}},ensure_ascii=False))


if __name__=='__main__':main()

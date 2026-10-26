"""仅经用户明确授权后验证当前本机MySQL；记录既有谱行哈希，不建库/建表/清表。"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import make_url
from scripts.local_deploy.config import read_config


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--authorized-current-mysql',action='store_true')
    parser.add_argument('--report',required=True)
    args=parser.parse_args()
    if not args.authorized_current_mysql:
        parser.error('必须先取得用户对当前库测试的明确授权，再提供开关')
    root=Path(__file__).resolve().parents[1]
    url=make_url(read_config(root)['DATABASE_URL'])
    assert (url.host,url.port,url.database)==('127.0.0.1',3307,'scwiki'), '目标与本次授权不符，拒绝写入'
    # 仅本进程和测试子进程的连接参数；不修改.env或系统环境。
    os.environ['DATABASE_URL']=url.render_as_string(hide_password=False)
    from backend import models
    engine=create_engine(url)

    def snapshot():
        result={}
        with engine.connect() as connection:
            assert connection.scalar(text('SELECT DATABASE()'))=='scwiki'
            for table in (models.SpectrumCollection.__table__,models.SpectrumRun.__table__):
                rows=connection.execute(select(table)).mappings().all()
                result[table.name]={row['id']:hashlib.sha256(json.dumps(dict(row),sort_keys=True,ensure_ascii=False,default=str).encode()).hexdigest() for row in rows}
        return result

    before=snapshot()
    # 测试依赖提供身份和临时草稿上下文；正式context仍校验权限，实际MySQL执行事务。
    env={**os.environ,'JWT_SECRET_KEY':'current-mysql-manual-verification-test-only',
         'SCWIKI_MANUAL_TEST_DATABASE_URL':url.render_as_string(hide_password=False),'SCWIKI_MANUAL_CURRENT_MYSQL':'1'}
    run=subprocess.run([sys.executable,'-m','pytest','backend/tests/test_spectra_manual.py','-q'],cwd=root,env=env,capture_output=True,text=True)
    after=snapshot()
    changes={name:dict(changed=[key for key,value in rows.items() if key in after[name] and after[name][key]!=value],
                       missing=sorted(set(rows)-set(after[name])),added=sorted(set(after[name])-set(rows))) for name,rows in before.items()}
    unchanged=all(not value for details in changes.values() for value in details.values())
    report=dict(time=datetime.now(timezone.utc).isoformat(),target=dict(host=url.host,port=url.port,database=url.database),
                authorization='用户明确要求使用当前MySQL库测试；本次仅随机测试target，不修改既有记录。',
                exit_code=run.returncode,baseline_counts={k:len(v) for k,v in before.items()},final_counts={k:len(v) for k,v in after.items()},
                existing_and_total_rows_unchanged=unchanged,changes=changes,before_hashes=before,after_hashes=after,
                pytest_output=run.stdout,pytest_stderr=run.stderr,
                boundary='实际MySQL与正式HTTP/服务代码；测试身份及上传草稿由依赖提供，不等同生产JWT/Redis或浏览器端到端验收。')
    destination=Path(args.report);destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(run.stdout)
    if run.stderr: print(run.stderr)
    print(json.dumps({k:report[k] for k in ('target','exit_code','baseline_counts','final_counts','existing_and_total_rows_unchanged','changes')},ensure_ascii=False))
    engine.dispose()
    return run.returncode or (0 if unchanged else 1)


if __name__=='__main__':
    raise SystemExit(main())

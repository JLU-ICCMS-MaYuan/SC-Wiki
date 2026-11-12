"""真实论文级模型提取及隔离入库验收；只启动和清理本脚本拥有的实例。"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def free_port():
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        return listener.getsockname()[1]


def verify(work, output, pdf, ir_path, url, redis_port, config):
    from sqlalchemy import select, func
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from backend.rag.config import settings
    settings.rag_database_url = url
    settings.redis_url = f'redis://127.0.0.1:{redis_port}/0'
    settings.sc_wiki_data_dir = work / 'runtime'
    from backend import models
    from backend.database import Base, engine, SessionLocal
    from backend.rag.llm_context import set_llm_config
    from backend.rag.llm import set_call_observer
    from backend.ingest import upload_tasks as tasks, upload_jobs as jobs
    from backend.ingest import property_evidence, paper_first, parsing_workflows
    from backend.ingest.document_ir import DocumentIR
    from backend.api import rag

    set_llm_config(config)
    runner = asyncio.Runner()
    # 旧模型的 JSON/TEXT 字面量默认值按 MySQL 表达式语法构建隔离夹具；
    # 不修改产品模型或业务库，本项实际迁移另在下方执行。
    from sqlalchemy import MetaData, JSON, Text, DefaultClause, literal, text
    fixture = MetaData()
    for table in Base.metadata.sorted_tables:
        table.to_metadata(fixture)
    for table in fixture.tables.values():
        for column in table.columns:
            default = column.server_default
            if isinstance(column.type, (JSON, Text)) and default is not None and isinstance(default.arg, str):
                expression = str(literal(default.arg).compile(engine, compile_kwargs={'literal_binds':True}))
                column.server_default = DefaultClause(text('(' + expression + ')'))
    fixture.create_all(engine)
    migration_path = ROOT / 'alembic/versions/20261112_0241_shallow_paper_publication.py'
    spec = importlib.util.spec_from_file_location('shallow_migration', migration_path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    with engine.begin() as connection:
        with Operations.context(MigrationContext.configure(connection)):
            migration.downgrade()
            migration.upgrade()
    with SessionLocal.begin() as session:
        session.add(models.User(id=1, username='isolated241', email='owner@issue241.invalid',
            real_name='浅度隔离验收', password_hash='unused', role='user', is_approved=True))

    digest = hashlib.sha256(pdf.read_bytes()).hexdigest()
    ir = DocumentIR.model_validate_json(ir_path.read_text())
    assert ir.source_sha256 == digest, '复用文本来源与PDF哈希不匹配'
    state = tasks.create_task(1, files=[{'client_id':'main', 'filename':pdf.name,
        'role':'main', 'size':pdf.stat().st_size}], defer_parsing=True)
    task_id = state['task_id']
    file_id = state['files'][0]['file_id']
    destination = tasks.task_directory(task_id) / 'main.pdf'
    shutil.copyfile(pdf, destination)
    tasks.update_task_file(task_id, file_id, upload_status='completed', stored_path=str(destination),
        source_file_path=str(destination), sha256=digest, size=destination.stat().st_size)
    ir.source_file_id = file_id
    artifact = tasks.artifact_directory(task_id) / 'document_ir' / f'{file_id}.json'
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(ir.model_dump_json())
    parsed = tasks.data_path('parsed_markdown') / task_id
    parsed.mkdir(parents=True, exist_ok=True)
    (parsed / f'{file_id}.md').write_text(jobs._ir_to_markdown(ir))
    tasks.lock_uploaded_manifest(task_id, parsing_mode='shallow')
    tasks.update_state(task_id, execution_resume_requested=True)
    forbidden_calls = []
    def forbidden(*args, **kwargs):
        forbidden_calls.append('forbidden')
        raise AssertionError('浅度进入了科学提取或核对')
    paper_first.prepare_paper = forbidden
    parsing_workflows.assess = forbidden
    property_evidence.generate_upload_suggestions = forbidden
    property_evidence.upload_snapshot = forbidden
    jobs._process_conventional_upload_task = forbidden
    calls = []
    set_call_observer(lambda event: calls.append({key:event.get(key) for key in
        ('phase', 'model', 'prompt_hash', 'prompt_tokens', 'completion_tokens', 'total_tokens')}))
    tasks.save_llm_config(task_id, config)
    ready = jobs.process_upload_task(task_id)
    recorded = json.loads((tasks.artifact_directory(task_id) / 'llm_calls.json').read_text())['calls']
    calls = [{key:event.get(key) for key in
        ('phase','model','prompt_hash','usage')} for event in recorded]
    assert ready['status'] == 'ready', ready.get('processing_error')
    draft = tasks.get_draft(task_id)
    (output / 'extracted-paper.json').write_text(json.dumps(draft, ensure_ascii=False, indent=2))
    (output / 'extraction.json').write_text(json.dumps(dict(model=config.model, calls=calls,
        source_sha256=digest, source_pdf=str(pdf)), ensure_ascii=False, indent=2))
    assert draft['material_states'] == []
    with SessionLocal() as session:
        user = session.get(models.User, 1)
    draft['paper']['summary'] += '\nIsolated roundtrip.'
    from backend.ingest.field_drafts import save_fields, target_lock, draft_version
    with target_lock('upload', task_id), SessionLocal.begin() as session:
        save_fields(session, 'upload', task_id, user, draft_version(tasks.get_draft(task_id)), [
            {'path':['paper','summary'], 'before':tasks.get_draft(task_id)['paper']['summary'],
             'value':draft['paper']['summary']}])
    saved = tasks.get_draft(task_id)
    assert saved['paper']['summary'].endswith('Isolated roundtrip.')
    create = rag._create_pending_paper
    async def failed(*args, **kwargs):
        raise RuntimeError('isolated transaction failure')
    rag._create_pending_paper = failed
    try:
        runner.run(rag._submit_upload_draft_locked(task_id, user))
        raise AssertionError('提交失败未传播')
    except RuntimeError as error:
        assert str(error) == 'isolated transaction failure'
    finally:
        rag._create_pending_paper = create
    assert tasks.get_state(task_id)['status'] == 'ready'
    result = runner.run(rag._submit_upload_draft_locked(task_id, user))
    repeated = runner.run(rag._submit_upload_draft_locked(task_id, user))
    assert result == repeated and result['review_status'] == 'published'
    with SessionLocal() as session:
        paper = session.get(models.Paper, result['paper_id'])
        assert paper.reviewed_at is None and paper.reviewed_by_user_id is None
        assert paper.approved_revision is None
        assert paper.summary == saved['paper']['summary']
        assert paper.research_materials == saved['paper']['research_materials']
        assert session.scalar(select(func.count()).select_from(models.Paper)) == 1
        assert session.scalar(select(func.count()).select_from(models.PaperFile)) == 1
        for model in (models.MaterialState, models.PropertyRecord, models.StructureModel,
                      models.ScientificEvidenceCheck):
            assert session.scalar(select(func.count()).select_from(model)) == 0, model.__name__
        history = list(session.scalars(select(models.PaperHistoryEvent)))
        assert len(history) == 1 and history[0].event_type == 'uploaded'
        assert history[0].review_status is None
        row = dict(paper_id=paper.id, title=paper.title, year=paper.year, doi=paper.doi,
            research_materials=paper.research_materials, review_status=paper.review_status)
    assert calls and not forbidden_calls
    assert {call['phase'] for call in calls} <= {'paper_info_extraction', 'paper_info_filling'}
    report = dict(status='backend_passed', source_pdf=str(pdf), source_sha256=digest,
        reused_document_ir=str(ir_path), text_extraction='复用哈希核验的原文IR，未复用字段答案',
        model=config.model, model_calls=calls, forbidden_calls=forbidden_calls, paper=row,
        failed_submit_recovered=True, repeat_submit_idempotent=True, business_database_used=False)
    (output / 'result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
    from backend.rag import database
    runner.run(database.engine.dispose())
    runner.close()
    engine.dispose()
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--pdf', type=Path, required=True)
    parser.add_argument('--document-ir', type=Path, required=True)
    parser.add_argument('--evidence-dir', type=Path, required=True)
    args = parser.parse_args()
    output = args.evidence_dir.resolve()
    output.mkdir(parents=True, exist_ok=False)
    from backend.rag.llm_context import get_server_default_config
    config = get_server_default_config()
    import pymysql
    binary = Path(sys.executable).parent
    processes = []
    with tempfile.TemporaryDirectory(prefix='scwiki241-') as temporary:
        work = Path(temporary)
        data = work / 'mysql'
        data.mkdir()
        port, redis_port = free_port(), free_port()
        assert port != 3307 and redis_port != 6379
        base = [str(binary/'mysqld'), '--no-defaults', '--basedir='+str(binary.parent), '--datadir='+str(data)]
        with (output/'mysql-initialize.log').open('w') as log:
            subprocess.run([*base, '--initialize-insecure'], stdout=log, stderr=subprocess.STDOUT, check=True)
        try:
            with (output/'mysql.log').open('w') as log:
                processes.append(subprocess.Popen([*base, '--port='+str(port), '--socket='+str(work/'mysql.sock'),
                    '--bind-address=127.0.0.1', '--mysqlx=0', '--skip-log-bin',
                    '--innodb-buffer-pool-size=64M', '--pid-file='+str(work/'mysql.pid')],
                    stdout=log, stderr=subprocess.STDOUT))
            with (output/'redis.log').open('w') as log:
                processes.append(subprocess.Popen([str(binary/'redis-server'), '--port',str(redis_port),
                    '--bind','127.0.0.1','--save','', '--appendonly','no','--dir',str(work)],
                    stdout=log, stderr=subprocess.STDOUT))
            for _ in range(160):
                try:
                    connection = pymysql.connect(host='127.0.0.1', port=port, user='root', autocommit=True)
                    break
                except pymysql.MySQLError:
                    if processes[0].poll() is not None: raise RuntimeError('隔离MySQL启动失败')
                    time.sleep(.25)
            else: raise RuntimeError('隔离MySQL未就绪')
            database = 'scwiki_issue241_test_' + os.urandom(6).hex()
            with connection:
                with connection.cursor() as cursor:
                    cursor.execute('SELECT @@port,@@datadir')
                    actual_port, actual_data = cursor.fetchone()
                    assert actual_port == port and Path(actual_data).resolve() == data.resolve()
                    cursor.execute('CREATE DATABASE '+database+' CHARACTER SET utf8mb4')
            url = f'mysql+pymysql://root@127.0.0.1:{port}/{database}'
            os.environ.update(DATABASE_URL=url, RAG_DATABASE_URL=url, FILE_STORAGE_BACKEND='local',
                REDIS_URL=f'redis://127.0.0.1:{redis_port}/0', SC_WIKI_DATA_DIR=str(work/'runtime'),
                JWT_SECRET_KEY=os.urandom(32).hex())
            verify(work, output, args.pdf.resolve(), args.document_ir.resolve(), url, redis_port, config)
            environment = {**os.environ, 'SCWIKI_SHALLOW_MYSQL_DSN':
                f'root@tcp(127.0.0.1:{port})/{database}?charset=utf8mb4&parseTime=True&loc=Local'}
            with (output/'go-search.log').open('w') as log:
                subprocess.run([str(ROOT/'.local/go/bin/go'), 'test', './handlers',
                    '-run','^TestShallowPublishedMySQL$', '-count=1'], cwd=ROOT/'goserver',
                    env=environment, stdout=log, stderr=subprocess.STDOUT, check=True)
            report = json.loads((output/'result.json').read_text())
            report.update(status='passed', go_search='passed')
            (output/'result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
            print('隔离真实提取、正式提交/重读及Go搜索通过；报告：'+str(output/'result.json'))
        finally:
            for process in reversed(processes):
                if process.poll() is None:
                    process.terminate()
                    try: process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        process.kill(); process.wait()


if __name__ == '__main__':
    main()

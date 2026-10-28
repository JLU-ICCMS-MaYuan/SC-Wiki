#!/usr/bin/env python3
"""从指定任务的正文/SI首页重提题录，经正式组装和隔离草稿保存验证；不改业务任务。"""
from copy import deepcopy
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--task-id', required=True)
    parser.add_argument('--expected-main-sha256', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    from dotenv import load_dotenv
    load_dotenv(ROOT / '.env', override=False)
    from backend.ingest import upload_tasks as tasks
    from backend.ingest.document_ir import DocumentIR
    from backend.ingest.upload_jobs import SUMMARY_SYSTEM_PROMPT, _normalize_draft
    from backend.ingest.grobid_document import apply_bibliography
    from backend.ingest.publication_year import verify_document_year
    from backend.ingest.parsing_diagnostics import annotate_differences
    from backend.rag.llm import complete_json
    from backend.rag.llm_context import get_llm_config
    from backend.storage.paths import resolve_file, clear_namespace, object_mode

    args.output.mkdir(parents=True, exist_ok=False)
    client = tasks.redis_client()
    state = json.loads(client.get(tasks.task_key(args.task_id)) or '{}')
    before = client.get(tasks.draft_key(args.task_id))
    files = state['files']
    main_file = next(f for f in files if f['role'] == 'main')
    assert main_file['sha256'] == args.expected_main_sha256, '正文身份不匹配'
    namespace = 'bibliography-verification-' + uuid4().hex
    report = {'passed': False, 'source_task': args.task_id, 'source_commit': subprocess.check_output(
        ['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(), 'sources': [],
        'reused': ['同源PDF的已保存IR文字', '同源GROBID原始题录'],
        'rerun': ['题录AI提取', '出版年核验', '正式题录组装', '正式归一化', '差异分类', '隔离草稿保存重读'],
        'not_run': ['全文OCR', '无关科学字段验收与业务写回', '正式论文提交'],
        'source_hashes': {name: hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in (
            'backend/ingest/grobid_document.py', 'backend/ingest/publication_year.py',
            'backend/ingest/parsing_diagnostics.py', 'backend/ingest/upload_jobs.py')}}
    try:
        docs, paths, contexts = {}, {}, []
        for file in files:
            if file.get('role') not in ('main', 'supplementary'):
                continue
            fid = file['file_id']
            ir_path = tasks.available_published_path(args.task_id, tasks.artifact_directory(args.task_id)/'document_ir'/f'{fid}.json')
            ir = DocumentIR.model_validate_json(ir_path.read_text())
            path = resolve_file(file['stored_path'], size=file['size'], sha256=file['sha256'], namespace=namespace) if object_mode() else Path(file['stored_path'])
            assert ir.source_sha256 == file['sha256'] == hashlib.sha256(path.read_bytes()).hexdigest()
            docs[fid], paths[fid] = ir, path
            contexts.append({'file_id': fid, 'file_role': file['role'], 'pdf_page': 1,
                'blocks': [{'block_id': b.block_id, 'text': b.text} for b in ir.blocks
                           if b.pdf_page == 1 and b.metadata.get('selected_for_reading') is not False]})
            report['sources'].append({'file_id': fid, 'role': file['role'], 'pdf_sha256': file['sha256'],
                'pages': [1], 'ir_sha256': hashlib.sha256(ir_path.read_bytes()).hexdigest()})
        system = SUMMARY_SYSTEM_PROMPT + '\nFIELD REGRESSION SCOPE: Extract ONLY paper bibliography: title, doi, authors, year, journal, volume, issue_number, pages, abstract from the supplied original main-paper and SI first pages. No material states, classification, summaries or scientific properties. Return {"paper": {...}}. Use null for absent facts. Do not infer publication year from a download/print date or from references. Do not use external knowledge. This scope limits output; it does not supply any expected answer.'
        prompt = json.dumps({'paper_context': contexts}, ensure_ascii=False)
        config = get_llm_config()
        report['model'] = {'provider': config.provider, 'model': config.model}
        dump(args.output/'input.json', {'system': system, 'prompt': prompt})
        raw = complete_json(system, prompt, on_call=lambda event: dump(args.output/f"call-{event['attempt']}.json", event))
        dump(args.output/'raw.json', raw)
        paper = raw.get('paper', raw)
        assert isinstance(paper, dict)
        fields = {'title', 'doi', 'authors', 'year', 'journal', 'volume', 'issue_number', 'pages', 'abstract'}
        report['ignored_extra_fields'] = sorted(set(paper) - fields)
        paper = {key: value for key, value in paper.items() if key in fields}
        doc = docs[main_file['file_id']].coverage['grobid']
        verification = verify_document_year(doc, paper, source_pdf=paths[main_file['file_id']])
        assert verification and verification['status'] == 'verified', '本次出版资料未核实'
        draft = {'paper': deepcopy(paper)}
        apply_bibliography(draft, doc, main_ir=docs[main_file['file_id']], publication_verification=verification)
        normalized = _normalize_draft(draft)
        for key in ('bibliography_sources', 'bibliography_conflicts'):
            normalized[key] = draft[key]
        normalized = annotate_differences(normalized, docs, files)
        shadow = uuid4().hex
        keys = [tasks.task_key(shadow), tasks.draft_key(shadow)]
        assert client.set(keys[0], json.dumps({'task_id': shadow, 'is_shadow': True,
            'created_at': int(time.time()), 'status': 'ready'}), ex=300, nx=True)
        try:
            saved = tasks.save_draft(shadow, deepcopy(normalized), value_origin='model')
            restored = tasks.get_draft(shadow)
            assert saved == restored, '保存重读不一致'
            dump(args.output/'restored.json', restored)
        finally:
            client.delete(*keys)
        assert restored['paper']['year'] == verification['year']
        for field in ('title', 'authors', 'abstract'):
            assert restored['paper'][field] == draft['paper'][field], field
        assert client.get(tasks.draft_key(args.task_id)) == before, '验证期间原业务草稿发生变化'
        report.update(passed=True, year=restored['paper']['year'], publication_verification=verification,
            saved_roundtrip_equal=True, business_draft_unchanged=True)
    except Exception as exc:
        report['error'] = {'type': type(exc).__name__, 'message': str(exc)}
        raise
    finally:
        clear_namespace(namespace)
        dump(args.output/'report.json', report)
        print(json.dumps({k: report.get(k) for k in ('passed','model','year','error')}, ensure_ascii=False))


if __name__ == '__main__':
    main()

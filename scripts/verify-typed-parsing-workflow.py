#!/usr/bin/env python3
"""从摘要核实的原PDF和已有通用文本真实判断流程，不修改原任务。"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def verify_scientific(state, assessment, output, *, complete=None):
    """按正式严格结构重提相邻Tc字段，并用正式草稿形态精确保存重读。"""
    from uuid import uuid4
    from backend.ingest import upload_tasks as tasks
    from backend.ingest.document_ir import DocumentIR
    from backend.ingest.domain_extraction import COMPLEMENTARY_SYSTEM_PROMPT, EXTRACTION_OUTPUT_SCHEMA, structured_chunks, normalize_extraction
    from backend.ingest.scientific_output_schema import filling_schema, decode_optional_containers
    from backend.ingest.scientific_form_filling import fill_scientific_forms
    from backend.ingest.state_optimization import assemble_candidates
    from backend.ingest.document_claims import claims_from_candidates, missing_tc_after_filling
    from backend.ingest.upload_jobs import _normalize_draft
    from backend.ingest.tc_contexts import map_draft
    from backend.ingest.parsing_workflows import POLICY, BINDING, require_task_workflow
    from backend.rag.llm import complete_json
    from backend.rag.config import settings
    complete = complete or complete_json
    output.mkdir()
    def dump(name, value):
        (output / name).write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str))
    documents, contexts, chunks, selection = {}, [], [], []
    for file in state['files']:
        if file['role'] not in {'main', 'supplementary'}: continue
        ir = DocumentIR.model_validate_json((settings.sc_wiki_data_dir / 'review_artifacts' /
            state['task_id'] / 'document_ir' / (file['file_id'] + '.json')).read_text())
        documents[file['file_id']] = ir
        # 本次相邻字段验证使用CaH6正文全部页面与SI的相关计算页面，通用判断已读取全部SI。
        pages = {p.pdf_page for p in ir.pages} if file['role'] == 'main' else {1, 2, 3, 19}
        chosen = ir.model_copy(deep=True)
        chosen.pages = [p for p in chosen.pages if p.pdf_page in pages]
        chosen.blocks = [b for b in chosen.blocks if b.pdf_page in pages]
        chosen.tables = [t for t in chosen.tables if t.pdf_page in pages]
        contexts.extend(json.loads(c.content) for c in structured_chunks(chosen))
        chunks.extend(dict(file_id=file['file_id'], file_role=file['role'], content=c.content)
                      for c in structured_chunks(ir))
        selection.append(dict(file_id=file['file_id'], pages_reextracted=sorted(pages)))
    quotes = {(c['file_id'], b['pdf_page'], b['block_id']): b['text']
              for c in contexts for p in c['pages'] for b in p['blocks']}
    prompt = json.dumps({'source_documents': contexts}, ensure_ascii=False)
    dump('extraction-input.json', {'system': COMPLEMENTARY_SYSTEM_PROMPT, 'input': prompt,
                                 'response_schema': EXTRACTION_OUTPUT_SCHEMA, 'selection': selection})
    raw = complete(COMPLEMENTARY_SYSTEM_PROMPT, prompt, response_schema=EXTRACTION_OUTPUT_SCHEMA)
    dump('extraction.json', raw)
    extracted = normalize_extraction(decode_optional_containers(raw), allowed_blocks=set(quotes),
        allowed_quote_text=quotes,
        allowed_tables={(c['file_id'], t['table_id']): int(t.get('row_count') or 0)
                        for c in contexts for p in c['pages'] for t in p.get('tables', [])},
        allowed_pages={(c['file_id'], p['geometry']['pdf_page']) for c in contexts for p in c['pages']},
        form_parameters=True)
    dump('extracted.json', extracted)
    before = assemble_candidates([extracted])
    def fill(prompt, content):
        return decode_optional_containers(complete(prompt, content, response_schema=filling_schema()))
    filled, audit = fill_scientific_forms(before, chunks, fill,
        on_attempt=lambda value: dump('filling.json', value))
    dump('filled.json', filled)
    assert audit['status'] == 'completed', '正式科学整理尚未完成'
    initial = claims_from_candidates({'material_states': before}, documents)
    final = claims_from_candidates({'material_states': filled}, documents)
    dump('claims.json', [c.model_dump(mode='json') for c in final])
    assert all(c.status == 'validated' for c in final), '最终来源定位未通过'
    assert not missing_tc_after_filling(initial, final, input_states=before, output_states=filled,
        filling_report=audit, documents=documents), '候选覆盖未通过'
    # 使用正式展开形态再保存，不能把读取时补齐的空模块metadata误当科学内容变化。
    draft = map_draft(_normalize_draft({'paper': assessment['paper'], 'material_states': filled}))
    draft[BINDING] = assessment['binding']
    shadow = uuid4().hex
    client = tasks.redis_client(); keys = [tasks.task_key(shadow), tasks.draft_key(shadow)]
    shadow_state = dict(task_id=shadow, is_shadow=True, status='ready', workflow_policy=POLICY,
                        **{BINDING: assessment['binding']})
    assert client.set(keys[0], json.dumps(shadow_state), ex=300, nx=True)
    try:
        saved = tasks.save_draft(shadow, draft)
        restored = tasks.get_draft(shadow)
        assert saved == restored, '正式草稿精确保存重读不一致'
        require_task_workflow(shadow_state, restored)
        dump('restored.json', restored)
        targets = [s for s in restored['material_states'] if s.get('material') == 'CaH6'
                   and s.get('pressure_value_gpa') == 150]
        assert len(targets) == 1, 'CaH6 150 GPa材料状态不唯一'
        records = [r for m in targets[0]['property_modules'] for r in m['records'] if r['property_code'] == 'tc']
        assert len(records) == 2, '正文两条Tc不应丢失或重复'
        assert {(r['value_number'], r['payload']['parameters'].get('mu_star')) for r in records} == {(220, .13), (235, .1)}, 'Tc与mu_star未保持正文配对'
        assert all(r['payload']['parameters'].get('lambda_ep') == 2.69 for r in records), '电声耦合参数不符合正文'
    finally:
        client.delete(*keys)
    return dict(passed=True, selection=selection, claims_validated=len(final),
        roundtrip_equal=True, binding_preserved=True,
        checked_values={'material': 'CaH6', 'pressure_gpa': 150, 'tc_mu_star': [[220, .13], [235, .1]], 'lambda_ep': 2.69},
        rerun=['严格结构科学字段AI提取', '正式表单整理与查缺', '原文定位与候选覆盖', '隔离Redis草稿精确保存重读'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--task-id', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--downstream', action='store_true', help='继续验证CaH6相邻Tc字段的正式提取、整理和隔离保存')
    args = parser.parse_args()
    from scripts.local_deploy.config import read_config, validate_local
    config = read_config(ROOT); validate_local(config, ROOT); os.environ.update(config)
    from backend.ingest import upload_tasks as tasks
    from backend.ingest.parsing_workflows import assess, require_workflow
    from backend.ingest.upload_source_bundle import task_source_chunks
    from backend.rag.llm_context import LlmConfig, resolve_llm_config, set_llm_config, reset_llm_config
    from backend.rag.config import settings
    from backend.storage.paths import resolve_file
    from backend.ingest.document_ir import DocumentIR
    client = tasks.redis_client()
    state = json.loads(client.get(tasks.task_key(args.task_id)))
    raw_config = client.get(tasks.llm_config_key(args.task_id))
    model = LlmConfig(**json.loads(raw_config)) if raw_config else resolve_llm_config()
    token = set_llm_config(model)
    args.output.mkdir(parents=True, exist_ok=False)
    report = dict(source_task=args.task_id, model=model.model, provider=model.provider,
        started=time.time(), source_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        source_hashes={}, sources=[], reused=['摘要核实的原PDF及通用IR/文本'],
        rerun=['真实模型流程适用性判断'], not_run=['原任务写入', '数据库业务提交', '整篇重新解析'])
    try:
        for name in ['parsing_workflows.py', 'upload_jobs.py', 'scientific_form_filling.py',
                     'domain_extraction.py', 'document_claims.py', 'tc_contexts.py']:
            report['source_hashes'][name] = hashlib.sha256((ROOT / 'backend/ingest' / name).read_bytes()).hexdigest()
        for item in state.get('files') or []:
            if item['role'] not in {'main', 'supplementary'}: continue
            original = resolve_file(item['stored_path'], size=int(item.get('size') or 0),
                sha256=item.get('sha256') or '', media_type=item.get('media_type') or 'application/pdf')
            digest = hashlib.sha256(original.read_bytes()).hexdigest()
            assert digest == item['sha256'], '原PDF摘要不符'
            path = settings.sc_wiki_data_dir / 'review_artifacts' / args.task_id / 'document_ir' / (item['file_id'] + '.json')
            ir = DocumentIR.model_validate_json(path.read_text())
            assert ir.source_sha256 == digest, 'IR不属于本次原PDF'
            report['sources'].append(dict(file_id=item['file_id'], role=item['role'], sha256=digest,
                ir_sha256=hashlib.sha256(path.read_bytes()).hexdigest(), pages=len(ir.pages)))
        chunks = task_source_chunks(args.task_id, state, settings.sc_wiki_data_dir / 'parsed_markdown', trim_references=True)
        assert chunks and any(c.get('file_role') == 'main' for c in chunks)
        report['source_chars'] = sum(len(c['content']) for c in chunks)
        assessment = assess(chunks, model=model.model)
        (args.output / 'assessment.json').write_text(json.dumps(assessment, ensure_ascii=False, indent=2))
        report['status'] = assessment['status']
        if assessment['status'] == 'matched':
            report['binding'] = require_workflow({'_parsing_workflow': assessment['binding']}, required=True).binding()
        report['passed'] = assessment['status'] == 'matched'
        if report['passed'] and args.downstream:
            downstream = verify_scientific(state, assessment, args.output / 'scientific')
            report['downstream'] = downstream
            report['passed'] = bool(downstream.get('passed'))
            report['rerun'].extend(downstream.get('rerun') or [])
    except Exception as exc:
        import traceback
        report['passed'] = False
        report['error_type'] = type(exc).__name__
        report['failed_frames'] = [dict(file=Path(frame.filename).name, line=frame.lineno, function=frame.name)
                                   for frame in traceback.extract_tb(exc.__traceback__)]
        failed = args.output / 'scientific' / 'report.json'
        if failed.is_file():
            report['downstream'] = json.loads(failed.read_text())
    finally:
        reset_llm_config(token)
        report['elapsed_seconds'] = time.time() - report['started']
        (args.output / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
        print(json.dumps(report, ensure_ascii=False))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())

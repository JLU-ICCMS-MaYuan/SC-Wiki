#!/usr/bin/env python3
"""#189：从原文重新提取受影响 Tc，正式整理、定位和隔离保存，不写原任务。"""
from pathlib import Path
import argparse
from copy import deepcopy
import hashlib
import json
import subprocess
import sys
import time
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--task-id', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--live', action='store_true', required=True)
    parser.add_argument('--extraction-response', type=Path, help='复用本轮已真实重提的原始响应，不能传入旧草稿')
    parser.add_argument('--filling-audit', type=Path, help='严格重放本轮真实整理的完整请求/响应，仅用于验证器及存取复核')
    args = parser.parse_args()
    from dotenv import load_dotenv
    load_dotenv(ROOT / '.env', override=True)
    from backend.ingest import upload_tasks as tasks
    from backend.rag.config import settings
    from backend.rag.llm import complete_json
    from backend.rag.llm_context import llm_display_metadata, catalog_config, set_llm_config, reset_llm_config
    from backend.ingest.document_ir import DocumentIR
    from backend.ingest.domain_extraction import (COMPLEMENTARY_SYSTEM_PROMPT, EXTRACTION_OUTPUT_SCHEMA,
                                                  structured_chunks, normalize_extraction)
    from backend.ingest.scientific_output_schema import filling_schema, decode_optional_containers
    from backend.ingest.scientific_form_filling import fill_scientific_forms, form_sources
    from backend.ingest.state_optimization import assemble_candidates
    from backend.ingest.document_claims import claims_from_candidates, missing_tc_after_filling
    from backend.ingest.tc_contexts import map_draft
    client = tasks.redis_client()
    before = {key: client.get(key) for key in (tasks.task_key(args.task_id), tasks.draft_key(args.task_id))}
    state = json.loads(before[tasks.task_key(args.task_id)])
    config = tasks.load_llm_config(args.task_id)
    if config is None:
        provider = str(state.get('llm_provider') or '')
        if not provider.startswith('server:'):
            raise ValueError('原任务模型配置不可用，不能用默认模型冒充原任务重跑')
        config = catalog_config(provider.removeprefix('server:'))
    token = set_llm_config(config)
    args.output.mkdir(parents=True, exist_ok=False)
    def dump(name, value):
        (args.output / name).write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + '\n')
    dump('original-before.json', {'state': state,
        'draft': json.loads(before[tasks.draft_key(args.task_id)]) if before[tasks.draft_key(args.task_id)] else None})
    report = {'passed': False, 'task_id': args.task_id, 'model': llm_display_metadata(),
              'source_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
              'source_hashes': {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in
                ['backend/ingest/tc_contexts.py', 'backend/ingest/tc_methods.py',
                 'backend/ingest/scientific_form_filling.py', 'backend/ingest/scientific_output_schema.py']},
              'reused': ['原 PDF 已提取的正文／表格 IR，未修改文字提取'],
              'rerun': ['受影响字段真实 AI 提取', '正式科学整理', '来源定位及防遗漏', '隔离 SQL 保存和重读'],
              'not_run': ['原任务修改', '整篇 PDF 重新解析', '业务送审批准']}
    started = time.time()
    replay = json.loads(args.filling_audit.read_text())['attempts'] if args.filling_audit else None
    replay_index = 0
    report['model_called_this_run'] = not bool(args.extraction_response and replay is not None)
    if replay is not None:
        report['reused'].append('本轮真实整理完整请求/响应；请求逐字相等后固定重放，不冒充新模型调用')
        report['rerun'] = ['本轮真实提取响应后处理', '正式整理严格请求重放', '来源定位及防遗漏', '隔离SQL保存重读']
    progress_at = 0.0
    def progress(phase, value):
        nonlocal progress_at
        if time.time() - progress_at > 10:
            progress_at = time.time()
            dump('progress.json', {'phase': phase, 'characters': len(value), 'elapsed_seconds': time.time() - started})
            print(phase, 'response characters', len(value), flush=True)
    try:
        documents, contexts, source_info = {}, [], []
        root = settings.sc_wiki_data_dir / 'review_artifacts' / args.task_id / 'document_ir'
        for file in state['files']:
            if file['role'] not in {'main', 'supplementary'}:
                continue
            path = root / (file['file_id'] + '.json')
            ir = DocumentIR.model_validate_json(path.read_text())
            assert ir.source_sha256 == file['sha256']
            # 正文方法及 LaH8 结果，补充材料方法说明和完整表 S1；相邻方法／材料一并覆盖。
            pages = {2, 3} if file['role'] == 'main' else {1, 5}
            chosen = ir.model_copy(deep=True)
            chosen.pages = [p for p in chosen.pages if p.pdf_page in pages]
            chosen.blocks = [b for b in chosen.blocks if b.pdf_page in pages]
            chosen.tables = [t for t in chosen.tables if t.pdf_page in pages]
            documents[file['file_id']] = chosen
            contexts.extend(json.loads(chunk.content) for chunk in structured_chunks(chosen))
            source_info.append({'file_id': file['file_id'], 'source_sha256': ir.source_sha256,
                                'ir_sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'pages': sorted(pages)})
        system = COMPLEMENTARY_SYSTEM_PROMPT + (
            '\nFIELD VALIDATION: Extract reported theoretical Tc results from Table S1 and the supplied '
            'main-text context, including each corresponding mu_star and method. Keep the reported '
            'method spelling in method_raw and the exact source references. Do not infer an unspecified '
            'Eliashberg subtype. Do not digitize curves or create unrelated property records.')
        prompt = json.dumps({'source_documents': contexts}, ensure_ascii=False)
        dump('extraction-input.json', {'system': system, 'prompt': prompt, 'sources': source_info})
        quotes = {(c['file_id'], b['pdf_page'], b['block_id']): b['text'] for c in contexts for p in c['pages'] for b in p['blocks']}
        error = None
        for attempt in range(3):
            print('reuse current-run extraction' if args.extraction_response else 'fresh extraction', attempt + 1, flush=True)
            if args.extraction_response:
                raw = json.loads(args.extraction_response.read_text())
                report['extraction_response_sha256'] = hashlib.sha256(args.extraction_response.read_bytes()).hexdigest()
                report['reused'].append('本轮刚重新提取的原始响应，非原任务旧提取结果')
            else:
                raw = complete_json(system, prompt + ('\nCorrect the prior response: ' + error if error else ''),
                                    response_schema=EXTRACTION_OUTPUT_SCHEMA,
                                    on_partial=lambda value: progress('extraction', value))
            dump(f'extraction-{attempt}.json', raw)
            try:
                extracted = normalize_extraction(decode_optional_containers(raw), allowed_blocks=set(quotes), allowed_quote_text=quotes,
                    allowed_tables={(c['file_id'], t['table_id']): int(t.get('row_count') or 0) for c in contexts for p in c['pages'] for t in p.get('tables', [])},
                    allowed_pages={(c['file_id'], p['geometry']['pdf_page']) for c in contexts for p in c['pages']}, form_parameters=True)
                break
            except Exception as exc:
                error = json.dumps(exc.as_dict(), ensure_ascii=False) if hasattr(exc, 'as_dict') else str(exc)
                dump(f'extraction-error-{attempt}.json', {'error': error})
                if attempt == 2 or args.extraction_response:
                    raise
        # 定向验证受影响状态及其相邻方法，不把整张表的其他材料冒充验收范围。
        extracted['material_states'] = [s for s in extracted['material_states']
            if s.get('material') == 'LaH8' and s.get('pressure_value_gpa') == 300]
        assert extracted['material_states'], '本轮新提取未包含受影响材料状态'
        report['scope'] = 'LaH8／300 GPa 的 McMillan 与 Eliashberg 结果'
        dump('extracted.json', extracted)
        candidates = assemble_candidates([extracted])
        dump('candidates.json', candidates)
        print('existing scientific filling', flush=True)
        def model(system, prompt):
            nonlocal replay_index
            if replay is not None:
                assert replay_index < len(replay), '当前整理需要额外请求，不能用旧答案代替'
                previous = replay[replay_index]; replay_index += 1
                assert json.loads(prompt) == previous['input'], '真实整理请求已变化，固定重放不得冒充当前验证'
                return deepcopy(previous['response'])
            return decode_optional_containers(complete_json(system, prompt, response_schema=filling_schema(),
                on_partial=lambda value: progress('filling', value)))
        actual_sources = [{'file_id': file['file_id'], 'file_role': file['role'],
                           'source_name': file['original_filename'], 'source_sha256': file['sha256']}
                          for file in state['files'] if file['file_id'] in documents]
        filling_sources = form_sources(documents, actual_sources)
        assert filling_sources and {s['file_id'] for s in filling_sources} == set(documents), '真实来源未完整接入整理'
        dump('filling-sources.json', filling_sources)
        filled, audit = fill_scientific_forms(candidates, filling_sources, model,
                                            on_attempt=lambda value: dump('filling.json', value))
        dump('filled.json', filled)
        assert audit['status'] == 'completed', '正式科学整理未完成，失败响应已保留'
        initial = claims_from_candidates({'material_states': candidates}, documents)
        final = claims_from_candidates({'material_states': filled}, documents)
        dump('claims.json', [c.model_dump(mode='json') for c in final])
        assert all(c.status == 'validated' for c in final), '最终来源存在未定位项'
        assert not missing_tc_after_filling(initial, final, input_states=candidates, output_states=filled,
                                            filling_report=audit, documents=documents)
        target = [s for s in filled if s.get('material') == 'LaH8' and s.get('pressure_value_gpa') == 300]
        assert len(target) == 1, 'LaH8／300 GPa 状态归属不唯一'
        records = [r for m in target[0]['property_modules'] for r in m['records'] if r.get('property_code') == 'tc']
        mcmillan = [r for r in records if r['method_code'] == 'mcmillan']
        assert {(r['value_number'], r['payload']['parameters'].get('mu_star')) for r in mcmillan} == {(131, .1), (114, .13)}
        assert len({r['payload']['tc_group']['method_key'] for r in mcmillan}) == 1
        eliashberg = [r for r in records if r['method_code'] != 'mcmillan']
        assert {(r['value_number'], r['payload']['parameters'].get('mu_star')) for r in eliashberg} == {(150, .1), (138, .13)}
        assert all('eliashberg' in str(r.get('method_raw') or '').lower() for r in eliashberg)
        assert all(r['method_code'] not in {'isotropic_eliashberg', 'anisotropic_eliashberg'} for r in eliashberg)
        draft = {'_field_edit_format': 1, 'paper': {'title': '隔离 Tc 方法验证'}, 'material_states': filled}
        dump('before-reading-projection.json', draft)
        # 正式读取投影显式建立空metadata容器；仍逐字比较全部科学值、原文、来源及关系。
        draft = map_draft(draft)
        dump('expected-roundtrip.json', draft)
        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session
        from backend.database import Base
        from backend.ingest.scientific_evidence import persist_upload
        from backend import models
        engine = create_engine('sqlite:///' + str(args.output / 'isolated.sqlite'))
        Base.metadata.create_all(engine)
        isolated = uuid4().hex
        with Session(engine) as db, db.begin():
            persist_upload(db, isolated, {'user_id': 1, 'task_id': isolated, 'status': 'ready'}, deepcopy(draft))
        with Session(engine) as db:
            saved = db.get(models.ScientificUploadDraft, isolated)
            restored = map_draft(saved.draft)
        engine.dispose()
        dump('restored.json', restored)
        assert restored == draft, '保存重读改变了原文、来源或科学对应'
        report.update(passed=True, sources=source_info, state_count=len(filled),
                      target_points=[{'tc': r['value_number'], 'mu_star': r['payload']['parameters'].get('mu_star'),
                                      'method_raw': r.get('method_raw')} for r in mcmillan], roundtrip_equal=True)
        report['adjacent_eliashberg_points'] = [{'tc': r['value_number'], 'mu_star': r['payload']['parameters'].get('mu_star'),
            'method_raw': r.get('method_raw')} for r in eliashberg]
    except Exception as exc:
        report['error'] = {'type': type(exc).__name__, 'message': str(exc)}
        raise
    finally:
        after = {key: client.get(key) for key in before}
        dump('original-after.json', {'state': json.loads(after[tasks.task_key(args.task_id)]) if after[tasks.task_key(args.task_id)] else None,
            'draft': json.loads(after[tasks.draft_key(args.task_id)]) if after[tasks.draft_key(args.task_id)] else None})
        report['original_task_unchanged'] = after == before
        if not report['original_task_unchanged']: report['passed'] = False
        report['elapsed_seconds'] = time.time() - started
        dump('report.json', report)
        print(json.dumps(report, ensure_ascii=False), flush=True)
        reset_llm_config(token)


if __name__ == '__main__':
    main()

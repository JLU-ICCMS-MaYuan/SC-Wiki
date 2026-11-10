"""从同原PDF/IR核验失败组来源交接；固定源验证，不冒充新模型请求。"""
from pathlib import Path
import hashlib, json, os
os.environ.setdefault('DATABASE_URL', 'sqlite:///:memory:')
from backend.ingest.document_ir import DocumentIR
from backend.ingest.scientific_form_filling import form_sources, _source_identity
from backend.ingest.scientific_context import build_context

OUT = Path(__file__).resolve().parent
case = json.loads((OUT.parents[1] / 'case.json').read_text())
documents, files = {}, []
for file in case['files']:
    assert hashlib.sha256(Path(file['path']).read_bytes()).hexdigest() == file['sha256']
    ir = next(DocumentIR.model_validate_json(path.read_text()) for path in OUT.glob('*.json')
              if len(path.stem) == 32 and json.loads(path.read_text()).get('source_sha256') == file['sha256'])
    documents[ir.source_file_id] = ir
    files.append({'file_id': ir.source_file_id, 'file_role': file['role'], 'content': ''})
report = json.loads((OUT / '0000-filling.json').read_text())
read = {s['source_id']: s for a in report['attempts'] for s in a['input']['sources']}
references = []
for value in report['attempts'][0]['input']['candidate_evidences'].values():
    if 'source_id' not in value:
        references.append(value)
    else:
        source = read[value['source_id']]
        span = value['quote_span']
        references.append({'file_id': source['file_id'], 'block_id': source['block_id'],
            'pdf_page': source['page_start'], 'source_version': source.get('source_version'),
            'quote': source['content'][span[0]:span[1]]})
original = {key: ir.model_dump(mode='json') for key, ir in documents.items()}
primary = build_context(form_sources(documents, files))['sources']
expanded = build_context(form_sources(documents, files, references=references))['sources']
required = {_source_identity(e) for e in references}
before = required - {_source_identity(s) for s in primary}
after = required - {_source_identity(s) for s in expanded}
assert len(before) == 2 and not after
preferred = [s for s in expanded if _source_identity(s) in required]
assert all(' '.join(e['quote'].split()) in ' '.join(s['content'].split())
           for e in references for s in preferred if _source_identity(e) == _source_identity(s))
assert original == {key: ir.model_dump(mode='json') for key, ir in documents.items()}
result = {'original_files_hash_equal': True, 'original_ir_unchanged': True,
    'required_source_identities': len(required), 'missing_before': len(before), 'missing_after': len(after),
    'primary_sources': len(primary), 'current_sources': len(expanded),
    'preferred_input_chars': sum(len(json.dumps(s, ensure_ascii=False)) for s in preferred),
    'new_model_calls': 0, 'scope': '原PDF哈希/原IR和真实候选原引用的生产form_sources/build_context交接；新模型及正式保存待网页续跑'}
(OUT / 'source-projection-result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))
print(json.dumps(result, ensure_ascii=False))

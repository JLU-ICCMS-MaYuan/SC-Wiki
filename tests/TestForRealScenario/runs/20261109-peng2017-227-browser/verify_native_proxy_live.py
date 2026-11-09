"""原PDF真实三解析器和正式IR转换；隔离运行，不写上传或正式数据。"""
from dotenv import load_dotenv
load_dotenv('.env')

from pathlib import Path
import hashlib
import json
import subprocess
import sys
import time

from backend.ingest.document_parsers import DocumentSource, ParseOptions, package_version
from backend.ingest.structured_pdf import run_parser_worker, convert_mineru, convert_docling
from backend.ingest.marker_pdf import convert_marker

ROOT = Path(__file__).resolve().parent
case = json.loads((ROOT / 'case-summary-fix.json').read_text())
out = ROOT / 'proxy-native-live'
out.mkdir(exist_ok=True)
results = json.loads((out / 'results.json').read_text()) if '--remaining' in sys.argv else []
for engine, role, pages in [('marker', 'main', [4]), ('marker', 'supplementary', [31]),
                             ('mineru', 'main', None), ('docling', 'supplementary', [31])]:
    if '--remaining' in sys.argv and engine == 'marker':
        continue  # 本轮刚完成的两份新Marker结果独立留证，不伪称再次解析。
    file = next(row for row in case['files'] if row['role'] == role)
    assert hashlib.sha256(Path(file['path']).read_bytes()).hexdigest() == file['sha256']
    directory = out / (f'{engine}-{role}' + ('-full' if pages is None else ''))
    source = DocumentSource(Path(file['path']), file_id=f'isolated-{role}', role=role, sha256=file['sha256'])
    options = ParseOptions(profile=engine, parser_options={
        'artifact_directory': str(directory), 'pages': pages, 'timeout_seconds': 900})
    started = time.monotonic()
    raw = run_parser_worker(engine, source.path, options)
    version = raw.get('version') or package_version(engine)
    ir = {'marker': convert_marker, 'mineru': convert_mineru, 'docling': convert_docling}[engine](raw, source, options, version)
    if pages is not None:
        assert [page.pdf_page for page in ir.pages] == pages
    else:
        import pymupdf
        with pymupdf.open(source.path) as pdf:
            assert [page.pdf_page for page in ir.pages] == list(range(1, len(pdf) + 1))
    assert ir.source_sha256 == file['sha256']
    serialized = ir.model_dump_json(indent=2)
    (directory / 'document-ir.json').write_text(serialized)
    assert type(ir).model_validate_json(serialized) == ir
    results.append({'engine': engine, 'role': role, 'pages': pages, 'version': version,
                    'blocks': len(ir.blocks), 'tables': len(ir.tables), 'source_sha256': file['sha256'],
                    'seconds': time.monotonic() - started, 'ir_roundtrip': True})
    (out / 'results.json').write_text(json.dumps(results, ensure_ascii=False, indent=2))
    print(json.dumps(results[-1], ensure_ascii=False), flush=True)
(out / 'code.json').write_text(json.dumps({
    'sha': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
    'structured_pdf_sha256': hashlib.sha256(Path('backend/ingest/structured_pdf.py').read_bytes()).hexdigest(),
    'scope': '原PDF重新执行三解析器及正式IR转换；未复用旧文本或旧模型回答；未执行科学提取或五阶段业务',
}, ensure_ascii=False, indent=2))

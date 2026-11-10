"""HEAD加本次明确覆盖文件的独立源码回归，不连接业务数据库。"""
from pathlib import Path
import hashlib, io, json, os, secrets, shutil, subprocess, tarfile, tempfile

ROOT = Path(__file__).resolve().parents[6]
OUT = Path(__file__).resolve().parent
FILES = ['backend/ingest/scientific_form_filling.py', 'backend/ingest/upload_jobs.py',
    'backend/tests/test_cited_alternative_source.py', 'backend/tests/test_complementary_pdf.py',
    'backend/tests/fixtures/cited_alternative/failed-source-handoff.json.gz',
    'tests/01_decentralized_uploading/test_scientific_form_filling.py']
SUITES = ['backend/tests/test_cited_alternative_source.py',
    'tests/01_decentralized_uploading/test_scientific_form_filling.py',
    'tests/TestForRealScenario/test_candidate_coverage.py',
    'tests/TestForRealScenario/test_material_group_worker.py',
    'tests/01_decentralized_uploading/test_material_group_processing.py',
    'tests/01_decentralized_uploading/test_material_group_review.py',
    'backend/tests/test_complementary_pdf.py', 'backend/tests/test_image_catalog_budget.py',
    'backend/tests/test_filling_budget_partitions.py', 'backend/tests/test_source_highlight.py',
    'backend/tests/test_model_memory.py']
with tempfile.TemporaryDirectory(prefix='scwiki-cited-alternative-') as temp:
    target = Path(temp)
    raw = subprocess.check_output(['git', 'archive', 'HEAD', 'backend', 'tests'], cwd=ROOT)
    with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
        archive.extractall(target, filter='data')
    for name in FILES:
        path = target / name
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / name, path)
    env = {**os.environ, 'PYTHONPATH': str(target), 'DATABASE_URL': 'sqlite:///:memory:',
           'JWT_SECRET_KEY': secrets.token_hex(32)}
    with (OUT / 'isolated-regressions.log').open('w') as log:
        result = subprocess.run(['/Users/mayuan/software/miniconda3/envs/sc-wiki/bin/python',
            '-m', 'pytest', *SUITES, '-q'], cwd=target, env=env, stdout=log, stderr=subprocess.STDOUT)
    (OUT / 'isolated-result.json').write_text(json.dumps({
        'base': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'overlays': {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in FILES},
        'exit_code': result.returncode, 'business_database_used': False,
        'scope': 'HEAD加本任务明确文件，SQLite内存配置，临时源码验证后移除'}, ensure_ascii=False, indent=2))
    print('isolated_exit', result.returncode)
    raise SystemExit(result.returncode)

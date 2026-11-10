"""固定HEAD加本任务源码验证，独立SQLite内存配置，不连接业务库。"""
from pathlib import Path
import hashlib, io, json, os, secrets, shutil, subprocess, tarfile, tempfile

ROOT = Path(__file__).resolve().parents[6]
OUT = Path(__file__).resolve().parent
PATHS = ['backend/ingest/structure_reading.py', 'backend/tests/test_structure_budget.py',
    'backend/tests/fixtures/structure_budget/failed-request.json.gz',
    'tests/TestForRealScenario/test_structure_request_redundancy.py']
SUITES = ['backend/tests/test_structure_budget.py', 'backend/tests/test_model_memory.py',
    'backend/tests/test_model_runtime.py', 'backend/tests/test_context_encoding.py',
    'backend/tests/test_structure_extractor.py', 'backend/tests/test_image_reading.py',
    'backend/tests/test_image_feedback.py', 'tests/TestForRealScenario/test_structure_request_redundancy.py',
    'tests/TestForRealScenario/test_structure_context_payload.py', 'tests/TestForRealScenario/test_structure_reading.py']
with tempfile.TemporaryDirectory(prefix='scwiki-structure-isolated-') as temp:
    target = Path(temp)
    content = subprocess.check_output(['git', 'archive', 'HEAD', 'backend', *SUITES[-3:]], cwd=ROOT)
    with tarfile.open(fileobj=io.BytesIO(content)) as archive:
        archive.extractall(target, filter='data')
    for name in PATHS:
        path = target / name
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / name, path)
    env = {**os.environ, 'PYTHONPATH': str(target), 'DATABASE_URL': 'sqlite:///:memory:',
           'JWT_SECRET_KEY': secrets.token_hex(32)}
    with (OUT / 'isolated-regressions-final.log').open('w') as log:
        result = subprocess.run(['/Users/mayuan/software/miniconda3/envs/sc-wiki/bin/python',
            '-m', 'pytest', *SUITES, '-q'], cwd=target, env=env, stdout=log, stderr=subprocess.STDOUT)
    (OUT / 'isolated-final.json').write_text(json.dumps({
        'base': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'overlays': {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in PATHS},
        'exit_code': result.returncode, 'business_database_used': False,
        'scope': 'HEAD加本任务明确文件，SQLite内存配置，临时源码验证后移除'}, ensure_ascii=False, indent=2))
    print('isolated_exit', result.returncode)
    raise SystemExit(result.returncode)

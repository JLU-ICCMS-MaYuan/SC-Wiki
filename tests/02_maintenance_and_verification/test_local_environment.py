"""Conda ownership and real Make preflight; never install into the user's environment."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.local_deploy import environment


def executable(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    path.chmod(0o755)
    return path


@pytest.mark.parametrize('check_only', [False, True])
@pytest.mark.parametrize('case', ['missing', 'not_executable', 'broken', 'base_alias', 'incompatible'])
def test_make_rejects_unusable_conda_without_writes(tmp_path, check_only, case):
    run_make_preflight(tmp_path, case, check_only=check_only)


@pytest.mark.parametrize('case', ['create', 'reuse'])
def test_make_checks_user_conda_and_reports_environment(tmp_path, case):
    run_make_preflight(tmp_path, case, check_only=True)


def run_make_preflight(tmp_path, case, *, check_only):
    root = tmp_path / 'project with spaces'
    shutil.copytree(ROOT / 'scripts/local_deploy', root / 'scripts/local_deploy',
                    ignore=shutil.ignore_patterns('__pycache__'))
    for name in ('local-deploy.py', 'locallydeploy.sh', 'local-deploy-versions.json'):
        shutil.copy2(ROOT / 'scripts' / name, root / 'scripts' / name)
    shutil.copy2(ROOT / 'Makefile', root / 'Makefile')
    # A retry marker bypasses unrelated occupied ports; the tested failure must not change it.
    (root / '.local').mkdir()
    (root / '.local/deployment-state.json').write_text('{}')
    bindir = tmp_path / 'commands'
    bindir.mkdir()
    for name in ('bash', 'make', 'curl', 'tar', 'setsid', 'ss', 'dirname'):
        path = shutil.which(name)
        if not path:
            pytest.skip(f'real Make entry requires {name}')
        (bindir / name).symlink_to(path)
    (bindir / 'python3').symlink_to(sys.executable)
    base = tmp_path / 'user conda'
    base.mkdir()
    prefix = tmp_path / 'custom environments/sc-wiki'
    if case == 'base_alias':
        prefix.parent.mkdir()
        prefix.symlink_to(base, target_is_directory=True)
    else:
        version = '3.11' if case == 'incompatible' else '3.12'
        executable(prefix / 'bin/python', '#!/bin/bash\nprintf "%s\\n" ' + version + '\n')
    conda = base / 'bin/conda'
    if case != 'missing':
        envs = [] if case == 'create' else [str(prefix)]
        executable(conda, f'#!{sys.executable}\nimport json, sys\n'
                   f'if {case == "broken"!r}:\n    print("private-conda-output", file=sys.stderr); sys.exit(9)\n'
                   f'if sys.argv[1:] == ["env", "list", "--json"]:\n    print({json.dumps({"envs": envs})!r})\n'
                   f'elif sys.argv[1:] == ["info", "--base"]:\n    print({str(base)!r})\n'
                   'else:\n    sys.exit(97)\n')
        if case == 'not_executable':
            conda.chmod(0o644)
    before = {p.relative_to(root): p.read_bytes() for p in root.rglob('*') if p.is_file()}
    process_env = {key: value for key, value in os.environ.items()
                   if key not in ('BUNDLE', 'CHECK_ONLY', 'MAKEFLAGS', 'MFLAGS', 'MAKELEVEL', 'PYTHONPATH')}
    result = subprocess.run(['make', 'deploy', f'CHECK_ONLY={int(check_only)}'], cwd=root,
                            env={**process_env, 'PATH': str(bindir), 'CONDA_EXE': str(conda),
                                 'PYTHONDONTWRITEBYTECODE': '1'},
                            text=True, capture_output=True, timeout=30)
    expected_success = case in ('create', 'reuse')
    assert result.returncode == (0 if expected_success else 2), result.stdout + result.stderr
    report = json.loads(result.stdout)
    if expected_success:
        assert report['result'] == 'check-passed'
        assert report['conda'] == str(conda)
        assert report['environment'] == ('将创建 sc-wiki' if case == 'create' else str(prefix))
    else:
        assert report['result'] == 'blocked'
        assert report['error_code'] == 'preflight_failed'
        assert report['phase'] == 'preflight'
        assert report['environment'] == '未就绪（Conda 预检未通过）'
        assert report['next_steps'] and 'CONDA_EXE' in report['next_steps'][0]
        assert 'Conda' in report['problems'][0]
        if case == 'base_alias':
            assert 'base' in report['problems'][0]
        if case == 'incompatible':
            assert '3.11' in report['problems'][0]
    assert 'private-conda-output' not in result.stdout + result.stderr
    assert {p.relative_to(root): p.read_bytes() for p in root.rglob('*') if p.is_file()} == before
    assert sorted(p.name for p in root.iterdir()) == ['.local', 'Makefile', 'scripts']


def test_missing_conda_never_downloads_or_installs(tmp_path, monkeypatch):
    monkeypatch.delenv('CONDA_EXE', raising=False)
    monkeypatch.delenv('CONDA_ROOT', raising=False)
    monkeypatch.setattr(environment.Path, 'home', lambda: tmp_path / 'user')
    monkeypatch.setattr(environment.shutil, 'which', lambda name: None)
    monkeypatch.setattr(environment, 'versions', lambda root: {})
    def forbidden(*args, **kwargs):
        pytest.fail('missing Conda must not run commands or download an installer')
    monkeypatch.setattr(environment, 'run', forbidden)
    monkeypatch.setattr(environment, 'download', forbidden)
    assert environment.find_environment(tmp_path) == (None, None)
    with pytest.raises(ValueError, match='用户准备的 Conda'):
        environment.install(tmp_path)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize('check_only', [False, True])
def test_missing_conda_report_does_not_create_deployment_state(tmp_path, monkeypatch, capsys, check_only):
    from types import SimpleNamespace
    from scripts.local_deploy import cli
    monkeypatch.setattr(environment, 'preflight', lambda *args, **kwargs: [])
    monkeypatch.setattr(environment, 'find_environment', lambda root: (None, None))
    assert cli.deploy(tmp_path, SimpleNamespace(bundle=None, check_only=check_only)) == 2
    report = json.loads(capsys.readouterr().out)
    assert report['problems'] == ['缺少用户准备的 Conda']
    assert report['environment'] == '未就绪（Conda 预检未通过）'
    assert report['conda'] is None
    assert report['next_steps']
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize('existing', [False, True])
def test_install_only_targets_scwiki_not_base(tmp_path, monkeypatch, existing):
    conda = tmp_path / 'user conda/bin/conda'
    prefix = tmp_path / 'user conda/envs/sc-wiki'
    spec = environment.versions(ROOT)
    calls = []
    def find(root):
        return conda, prefix if existing or calls else None
    def run(args, **kwargs):
        calls.append(args)
        if Path(args[0]).name == 'python':
            assert args == [prefix / 'bin/python', '-m', 'pip', 'install', '-r', tmp_path / 'docker/requirements.txt']
            raise ValueError('stop before installing dependencies')
        return ''
    monkeypatch.setattr(environment, 'find_environment', find)
    monkeypatch.setattr(environment, 'versions', lambda root: spec)
    monkeypatch.setattr(environment, 'run', run)
    with pytest.raises(ValueError, match='stop before installing'):
        environment.install(tmp_path)
    assert calls[0] == ([conda, 'install', '-y', '-p', prefix] if existing else
                        [conda, 'create', '-y', '-n', 'sc-wiki']) + [
                            '--override-channels', '-c', 'conda-forge', *spec['conda_packages']]
    assert len(calls) == 2

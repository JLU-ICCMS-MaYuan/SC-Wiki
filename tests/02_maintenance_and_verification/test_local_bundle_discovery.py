"""Real archive and Make entry checks; all data belongs to temporary test projects."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.local_deploy import bundle, cli, config, environment
from scripts.local_deploy.state import DeploymentState


@pytest.fixture
def project(tmp_path):
    root = tmp_path / 'project with spaces'
    shutil.copytree(ROOT / 'scripts/local_deploy', root / 'scripts/local_deploy',
                    ignore=shutil.ignore_patterns('__pycache__'))
    for name in ('Makefile', 'scripts/local-deploy.py', 'scripts/locallydeploy.sh',
                 'scripts/local-deploy-versions.json', 'scripts/local-deploy-schema.json',
                 'docker/requirements.txt', 'frontend/package-lock.json',
                 'goserver/go.mod', 'goserver/go.sum'):
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / name, target)
    return root


def make_archive(root, tmp_path, name='only backup.tar.gz'):
    seed = tmp_path / ('seed-' + name)
    shutil.copytree(root, seed, ignore=shutil.ignore_patterns('.local', '.data', '.env', 'dist', '__pycache__'))
    payload = seed / '.deployment/mysql/business.sql'
    payload.parent.mkdir(parents=True)
    payload.write_text('SELECT 1;\n')
    manifest = bundle.seal(seed, {'source_commit': 'a' * 40, 'source_identity': cli.source_identity(root),
                                  'services': environment.versions(root),
                                  'components': {'mysql': {'database': 'scwiki'}}})
    archive = root / 'dist' / name
    bundle.publish(seed, archive)
    return archive, manifest


def snapshot(root):
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob('*') if p.is_file()}


def run_make(root, *, check_only, extra=(), conda=None):
    process_env = {key: value for key, value in os.environ.items()
                   if key not in ('BUNDLE', 'CHECK_ONLY', 'MAKEFLAGS', 'MFLAGS', 'MAKELEVEL', 'PYTHONPATH')}
    process_env['PYTHONDONTWRITEBYTECODE'] = '1'
    # Failure tests must never discover or install into a real user environment, even before the fix.
    process_env['CONDA_EXE'] = str(conda or root / 'nonexistent-test-conda')
    before = snapshot(root)
    result = subprocess.run(['make', 'deploy', f'CHECK_ONLY={int(check_only)}', *extra], cwd=root,
                            env=process_env, capture_output=True, text=True, timeout=30)
    assert snapshot(root) == before, 'preflight must not change configuration, state, data or reports'
    assert 'Traceback' not in result.stderr
    return result, json.loads(result.stdout)


@pytest.mark.parametrize('check_only', [False, True])
@pytest.mark.parametrize('explicit', [False, True])
def test_make_multiple_archives_rejected_before_any_writes(project, check_only, explicit):
    dist = project / 'dist'
    dist.mkdir()
    first = dist / 'older.tar.gz'
    first.write_bytes(b'not opened when multiple archives exist')
    (dist / 'newer.tgz').write_bytes(b'not opened')
    (dist / 'older.tar.gz.sha256').write_text('checksum does not count')
    (project / '.local').mkdir()
    (project / '.local/deployment-report.json').write_text('{"existing_report": true}')
    extra = [f'BUNDLE={first}'] if explicit else []
    result, report = run_make(project, check_only=check_only, extra=extra)
    assert result.returncode == 2
    assert report['result'] == 'blocked'
    assert report['error_code'] == 'preflight_failed' and report['phase'] == 'preflight'
    assert '必须只能保留一个' in ' '.join(report['problems'])
    assert report['conda'] is None and report['environment'].startswith('未检查')


def test_discovery_ignores_checksums_and_non_archive_files(tmp_path):
    assert bundle.discover_archive(tmp_path) is None
    dist = tmp_path / 'dist'
    dist.mkdir()
    (dist / 'README.md').write_text('only backups belong here')
    (dist / 'missing.tar.gz.sha256').write_text('sidecar')
    (dist / 'nested').mkdir()
    (dist / 'nested/ignored.tar.gz').write_bytes(b'nested, not a direct candidate')
    assert bundle.discover_archive(tmp_path) is None
    archive = dist / 'one backup.tar.gz'
    archive.write_bytes(b'validated later')
    assert bundle.discover_archive(tmp_path) == archive


@pytest.mark.parametrize('kind', ['directory', 'symlink', 'broken_symlink'])
def test_discovery_rejects_non_regular_archive(tmp_path, kind):
    dist = tmp_path / 'dist'
    dist.mkdir()
    archive = dist / 'invalid.tar.gz'
    if kind == 'directory':
        archive.mkdir()
    else:
        outside = tmp_path / 'external.tar.gz'
        if kind == 'symlink':
            outside.write_bytes(b'outside')
        archive.symlink_to(outside)
    with pytest.raises(ValueError, match='普通文件'):
        bundle.discover_archive(tmp_path)


def test_discovery_rejects_symlink_dist(tmp_path):
    outside = tmp_path / 'outside'
    outside.mkdir()
    root = tmp_path / 'project'
    root.mkdir()
    (root / 'dist').symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match='dist'):
        bundle.discover_archive(root)


@pytest.mark.parametrize('check_only', [False, True])
@pytest.mark.parametrize('name', ['corrupt.tar.gz', 'unsupported.zip', 'database.sql.gz'])
def test_make_bad_archive_does_not_fall_back_to_empty(project, check_only, name):
    (project / 'dist').mkdir()
    (project / 'dist' / name).write_bytes(b'not a portable migration archive')
    result, report = run_make(project, check_only=check_only)
    assert result.returncode == 2
    assert report['result'] == 'blocked' and report['error_code'] == 'preflight_failed'
    assert any('压缩包' in problem for problem in report['problems'])


def test_single_archive_is_really_extracted_and_preserves_config(project, tmp_path):
    archive, manifest = make_archive(project, tmp_path)
    config.ensure_config(project)
    original_config = (project / '.env').read_bytes()
    before = snapshot(project)
    assert cli.prepare_bundle(project, None, check_only=True)[1] == manifest
    assert snapshot(project) == before
    assert cli.prepare_bundle(project, None)[1] == manifest
    assert (project / '.deployment/mysql/business.sql').read_text() == 'SELECT 1;\n'
    assert (project / '.env').read_bytes() == original_config
    assert bundle.verify(project) == manifest
    after = snapshot(project)
    assert cli.prepare_bundle(project, None)[1] == manifest
    assert snapshot(project) == after
    assert archive.is_file()


def test_explicit_bundle_and_unpacked_fallback_remain_supported(project, tmp_path):
    archive, manifest = make_archive(project, tmp_path)
    external = tmp_path / 'explicit.tar.gz'
    archive.rename(external)
    assert cli.prepare_bundle(project, str(external))[1] == manifest
    assert cli.prepare_bundle(project, None, check_only=True)[1] == manifest
    assert cli.prepare_bundle(project, None)[1] == manifest


@pytest.mark.parametrize('check_only', [False, True])
def test_make_unpacked_symlink_does_not_fall_back_to_empty(project, tmp_path, check_only):
    (project / '.deployment').symlink_to(tmp_path / 'missing-deployment', target_is_directory=True)
    result, report = run_make(project, check_only=check_only)
    assert result.returncode == 2 and report['result'] == 'blocked'
    assert '符号链接' in ' '.join(report['problems'])
    assert (project / '.deployment').is_symlink()


@pytest.mark.parametrize('check_only', [False, True])
@pytest.mark.parametrize('metadata', [[], {'format_version': 1, 'bundle_id': 123, 'files': {}}])
def test_make_malformed_manifest_preserves_existing_report(project, check_only, metadata):
    bundle.write_json(project / '.deployment/manifest.json', metadata)
    bundle.write_json(project / '.local/deployment-report.json', {'existing_report': True})
    result, report = run_make(project, check_only=check_only)
    assert result.returncode == 2 and report['result'] == 'blocked'
    assert report['phase'] == 'preflight' and report['error_code'] == 'preflight_failed'
    assert '清单' in ' '.join(report['problems'])


@pytest.mark.parametrize('check_only', [False, True])
def test_make_changed_source_does_not_overwrite_it(project, tmp_path, check_only):
    make_archive(project, tmp_path)
    (project / 'Makefile').write_text((project / 'Makefile').read_text() + '\n# local change\n')
    result, report = run_make(project, check_only=check_only)
    assert result.returncode == 2 and report['result'] == 'blocked'
    assert '源码' in ' '.join(report['problems'])


@pytest.mark.parametrize('check_only', [False, True])
def test_make_conflicting_unpacked_manifest_rejected_read_only(project, tmp_path, check_only):
    _, manifest = make_archive(project, tmp_path)
    cli.prepare_bundle(project, None)
    path = project / '.deployment/manifest.json'
    manifest['capacity'] += 1  # Same UUID is insufficient: the complete metadata must agree.
    bundle.write_json(path, manifest)
    result, report = run_make(project, check_only=check_only)
    assert result.returncode == 2 and report['result'] == 'blocked'
    assert '清单' in ' '.join(report['problems'])


@pytest.mark.parametrize('check_only', [False, True])
def test_make_existing_empty_install_cannot_be_replaced_by_bundle(project, tmp_path, check_only):
    make_archive(project, tmp_path)
    state = DeploymentState.open(project, cli.source_identity(project))
    state.staging.mkdir()
    (state.staging / 'precious').write_text('current instance data')
    state.promote()
    state.save('complete')
    config.ensure_config(project)
    result, report = run_make(project, check_only=check_only)
    assert result.returncode == 2 and report['result'] == 'blocked'
    assert '已有部署记录' in ' '.join(report['problems'])
    assert not (project / '.deployment').exists()


@pytest.mark.parametrize('with_archive', [False, True])
def test_make_check_only_reports_selected_mode(project, tmp_path, with_archive):
    identity = cli.source_identity(project)
    if with_archive:
        _, manifest = make_archive(project, tmp_path)
        identity = manifest['bundle_id']
    DeploymentState.open(project, identity)  # Owned installation checkpoint skips unrelated live ports.
    conda = tmp_path / 'conda'
    conda.write_text(f'#!{sys.executable}\nimport json, sys\n'
                     'assert sys.argv[1:] == ["env", "list", "--json"]\n'
                     'print(json.dumps({"envs": []}))\n')
    conda.chmod(0o755)
    result, report = run_make(project, check_only=True, conda=conda)
    assert result.returncode == 0, result.stdout + result.stderr
    assert report['result'] == 'check-passed'
    assert report['mode'] == ('restore' if with_archive else 'empty')
    assert report.get('bundle') == (str(project / 'dist/only backup.tar.gz') if with_archive else None)

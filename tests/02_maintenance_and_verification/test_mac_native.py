"""Exercise native process ownership and Make routing without a VM."""
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.local_deploy import environment
from scripts.local_deploy.runtime import Runtime


def test_mac_manifest_keeps_service_versions(monkeypatch):
    monkeypatch.setattr(environment.platform, 'system', lambda: 'Darwin')
    monkeypatch.setattr(environment.platform, 'machine', lambda: 'arm64')
    spec = environment.versions(ROOT)
    assert spec['platform'] == 'darwin-arm64'
    assert spec['go']['url'].endswith('darwin-arm64.tar.gz')
    assert spec['qdrant']['url'].endswith('aarch64-apple-darwin.tar.gz')
    assert spec['schema_heads'] == ['20260914_0052', '20260924_0114']
    assert spec['grobid']['java_environment'] == 'sc-wiki'
    assert spec['grobid']['java_version'] == '21.0.9'
    assert spec['grobid']['version'] == '0.8.1'
    overrides = json.loads((ROOT / 'scripts/local-deploy-macos.json').read_text())['arm64']
    # Merging GROBID must preserve other services in existing bundle manifests.
    assert spec['go'] == overrides['go']
    assert spec['qdrant'] == overrides['qdrant']
    monkeypatch.setattr(environment.platform, 'system', lambda: 'Linux')
    assert environment.versions(ROOT) == json.loads((ROOT / 'scripts/local-deploy-versions.json').read_text())


def test_native_process_ownership_and_stop(tmp_path):
    root = tmp_path / 'project with spaces'
    pidfile = root / '.local/run/mysql.pid'
    pidfile.parent.mkdir(parents=True)
    runtime = Runtime(root, Path(sys.prefix), {})
    process = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(90)'],
                               cwd=root, start_new_session=True)
    try:
        pidfile.write_text(str(process.pid))
        assert runtime.owned_pid('mysql') == process.pid
        runtime.stop_gracefully('mysql', timeout=5)
        assert process.wait(timeout=5) == -signal.SIGTERM
        assert not pidfile.exists()
    finally:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGKILL)
        process.wait()


def test_foreign_process_is_not_stopped(tmp_path):
    root = tmp_path / 'project'
    pidfile = root / '.local/run/mysql.pid'
    pidfile.parent.mkdir(parents=True)
    process = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(90)'],
                               cwd=tmp_path, start_new_session=True)
    try:
        pidfile.write_text(str(process.pid))
        with pytest.raises(ValueError, match='不属于'):
            Runtime(root, Path(sys.prefix), {}).stop_gracefully('mysql', timeout=1)
        assert process.poll() is None
    finally:
        os.killpg(process.pid, signal.SIGTERM)
        process.wait()


@pytest.mark.parametrize('value', ['-1', '0', '1', 'not-a-pid'])
def test_invalid_pid_is_rejected_before_signalling(tmp_path, value):
    pidfile = tmp_path / '.local/run/worker.pid'
    pidfile.parent.mkdir(parents=True)
    pidfile.write_text(value)
    with pytest.raises(ValueError, match='PID'):
        Runtime(tmp_path, Path(sys.prefix), {}).stop_gracefully('worker', timeout=1)


def test_process_exiting_between_ps_and_lsof_is_stopped(monkeypatch):
    from scripts.local_deploy import host
    monkeypatch.setattr(host.platform, 'system', lambda: 'Darwin')
    replies = iter([(0, 'S python worker'), (1, ''), (1, '')])
    def run(args, **kwargs):
        code, output = next(replies)
        return subprocess.CompletedProcess(args, code, stdout=output)
    monkeypatch.setattr(host.subprocess, 'run', run)
    assert host.process_info(12345) is None


def test_unknown_listener_is_not_adopted(tmp_path):
    with socket.socket() as sock:
        try:
            sock.bind(('127.0.0.1', 3307))
        except OSError:
            pytest.skip('3307 already in use')
        sock.listen()
        with pytest.raises(ValueError, match='归属不明'):
            Runtime(tmp_path, Path(sys.prefix), {}).check_ports()


def test_released_port_can_restart_after_tcp_connection():
    with socket.socket() as server:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(('127.0.0.1', 0))
        port = server.getsockname()[1]
        server.listen()
        with socket.create_connection(('127.0.0.1', port)) as client:
            connection, _ = server.accept()
            connection.close()
            assert client.recv(1) == b''
    result = subprocess.run([sys.executable, str(ROOT / 'scripts/local_deploy/host.py'),
                             'port-busy', str(port)])
    assert result.returncode == 1


def test_make_routes_without_running_services():
    for target in ('start', 'stop', 'status', 'deploy', 'frozen'):
        result = subprocess.run(['make', '-n', target], cwd=ROOT, capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
        assert 'lima' not in result.stdout.lower()
        assert 'docker compose' not in result.stdout
        assert 'scripts/' in result.stdout


def test_linux_make_keeps_original_entrypoints(tmp_path):
    uname = tmp_path / 'uname'
    uname.write_text('#!/bin/sh\necho Linux\n')
    uname.chmod(0o755)
    env = {**os.environ, 'PATH': str(tmp_path) + os.pathsep + os.environ['PATH']}
    for target, entry in (('start', 'scripts/dev.sh start'),
                          ('deploy', 'scripts/locallydeploy.sh'),
                          ('frozen', 'scripts/pack.sh')):
        result = subprocess.run(['make', '-n', target], cwd=ROOT, env=env,
                                capture_output=True, text=True, check=True)
        assert entry in result.stdout


def test_deployment_report_recognizes_numbered_credentials():
    from scripts.local_deploy.cli import capabilities
    report = capabilities({'LLM1_API_KEY': 'private-test-value'})
    assert report['AI'] == '已配置，尚未实际调用验收'
    assert 'private-test-value' not in json.dumps(report)


def test_shared_java_install_reuses_main_environment(tmp_path, monkeypatch):
    from scripts.local_deploy import native
    prefix = tmp_path / 'sc-wiki'
    history = prefix / 'conda-meta/history'
    history.parent.mkdir(parents=True)
    history.touch()
    spec = {'version': '0.8.1', 'java_environment': 'sc-wiki', 'java_version': '21.0.9'}
    target = tmp_path / '.local/grobid'
    target.mkdir(parents=True)
    (target / 'native-install.json').write_text(json.dumps(spec))
    monkeypatch.setattr(native, 'verify_grobid', lambda *args: None)
    commands = []
    def run(args, **kwargs):
        commands.append(args)
        assert args == [prefix / 'bin/java', '--version']
        return 'openjdk 21.0.9 2025-10-21\n'
    monkeypatch.setattr(native, 'run', run)
    native.install_grobid(tmp_path, Path('/must-not-run-conda'), spec, prefix=prefix)
    assert len(commands) == 1
    assert not (tmp_path / '.local/grobid-java').exists()


def test_shared_java_missing_environment_never_creates_fallback(tmp_path, monkeypatch):
    from scripts.local_deploy import native
    spec = {'java_environment': 'sc-wiki', 'java_version': '21.0.9'}
    monkeypatch.setattr(native, 'run', lambda *args, **kwargs: pytest.fail('must not install Java'))
    with pytest.raises(ValueError, match='sc-wiki'):
        native.install_grobid(tmp_path, Path('/conda'), spec, prefix=tmp_path / 'missing')
    with pytest.raises(ValueError, match='前缀'):
        native.install_grobid(tmp_path, Path('/conda'), spec)
    assert not (tmp_path / '.local/grobid-java').exists()


def test_shared_java_wrong_version_is_rejected(tmp_path, monkeypatch):
    from scripts.local_deploy import native
    prefix = tmp_path / 'sc-wiki'
    history = prefix / 'conda-meta/history'
    history.parent.mkdir(parents=True)
    history.touch()
    spec = {'java_environment': 'sc-wiki', 'java_version': '21.0.9'}
    monkeypatch.setattr(native, 'run', lambda *a, **k: 'openjdk 17.0.18\n')
    with pytest.raises(ValueError, match='Java 版本不兼容'):
        native.install_grobid(tmp_path, Path('/conda'), spec, prefix=prefix)


def test_legacy_java_selection_remains_isolated(tmp_path):
    assert environment.grobid_java_prefix(tmp_path, tmp_path / 'main', {}) == tmp_path / '.local/grobid-java'


def test_gradle8_patch_changes_only_report_switches(tmp_path):
    from scripts.local_deploy.native import configure_grobid_build
    path = tmp_path / 'build.gradle'
    path.write_text('reports {\nxml.enabled true\nhtml.enabled true\ncsv.enabled true\n}\n')
    spec = {'gradle': {'version': '8.5'}}
    configure_grobid_build(tmp_path, spec)
    assert path.read_text() == 'reports {\nxml.required = true\nhtml.required = true\ncsv.required = true\n}\n'
    with pytest.raises(ValueError, match='结构变化'):
        configure_grobid_build(tmp_path, spec)
    path.write_text('unchanged Linux build')
    configure_grobid_build(tmp_path, {'gradle': {'version': '7.6.4'}})
    assert path.read_text() == 'unchanged Linux build'

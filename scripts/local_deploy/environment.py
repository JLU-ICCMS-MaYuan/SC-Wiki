"""环境发现、前置检查和依赖安装。不会修改 shell 配置。"""
from __future__ import annotations

import json
import os
from pathlib import Path
import platform
import shutil
import socket
import subprocess
import tarfile
import tempfile

from .bundle import digest, write_json

PORTS = (3307, 6379, 17687, 7474, 6333, 6334, 8000, 8080, 5173, 8070, 8071)


def preflight_guidance(problems: list[str]) -> list[str]:
    """为可修复的前置失败提供不涉及凭据的下一步提示。"""
    guidance = []
    if any(problem.startswith('缺少系统前置工具 ') for problem in problems):
        guidance.append('请先安装报告中缺少的系统工具，再重新运行 make deploy CHECK_ONLY=1')
    if any('Conda' in problem for problem in problems):
        guidance.append('Conda 由用户准备；请用 conda --version 和 conda env list 验证，必要时设置 CONDA_EXE=/实际安装目录/bin/conda 后重跑 make deploy CHECK_ONLY=1；脚本不会安装或升级 Conda，也不会向 base 安装项目依赖')
    if any(problem.startswith('端口 ') for problem in problems):
        guidance.append('请用 ss -ltnp 确认端口占用者，确认可以停止对应服务后再处理冲突并重新预检')
    if '可用磁盘不足 8 GiB，无法准备依赖与临时数据' in problems:
        guidance.append('请释放至少 8 GiB 可用磁盘空间后再重试')
    return guidance


def run(args, *, cwd=None, env=None, timeout=1800, capture=False):
    result = subprocess.run([str(a) for a in args], cwd=cwd, env=env, timeout=timeout,
                            text=True, stdout=subprocess.PIPE if capture else None,
                            stderr=subprocess.PIPE if capture else None)
    if result.returncode:
        # 不把第三方输出中可能包含的配置/凭据拼入公开异常。
        raise ValueError(f'{Path(str(args[0])).name} 执行失败（退出 {result.returncode}）')
    return result.stdout if capture else ''


def versions(root: Path) -> dict:
    return json.loads((root / 'scripts/local-deploy-versions.json').read_text())


def select_prefix(prefixes) -> Path | None:
    matches = sorted({str(Path(p).resolve()) for p in prefixes if Path(p).name == 'sc-wiki'})
    if len(matches) > 1:
        raise ValueError('发现多个 sc-wiki 环境，请通过 CONDA_EXE 选择 Conda 安装')
    return Path(matches[0]) if matches else None


def find_conda(root: Path) -> Path | None:
    explicit = os.environ.get('CONDA_EXE')
    if explicit:
        if not Path(explicit).is_file() or not os.access(explicit, os.X_OK):
            raise ValueError('CONDA_EXE 不存在或不可执行')
        return Path(explicit).resolve()
    candidates = [shutil.which('conda')]
    if os.environ.get('CONDA_ROOT'):
        candidates.append(str(Path(os.environ['CONDA_ROOT']) / 'bin/conda'))
    candidates += [str(Path.home() / name / 'bin/conda') for name in ('miniconda3', 'miniforge3', 'anaconda3')]
    candidates.append(str(root / '.local/miniforge/bin/conda'))
    return next((Path(p).resolve() for p in candidates
                 if p and Path(p).is_file() and os.access(p, os.X_OK)), None)


def find_environment(root: Path) -> tuple[Path | None, Path | None]:
    conda = find_conda(root)
    if not conda:
        return None, None
    data = json.loads(run([conda, 'env', 'list', '--json'], capture=True, timeout=45))
    candidates = data['envs']
    if os.environ.get('CONDA_EXE'):
        # env list 包含跨安装登记的环境；显式 Conda 优先选择它自己管理的命名环境。
        named = conda.parent.parent / 'envs/sc-wiki'
        if str(named) in candidates:
            candidates = [str(named)]
    prefix = select_prefix(candidates)
    if prefix:
        base = Path(run([conda, 'info', '--base'], capture=True, timeout=45).strip())
        if not base.is_absolute():
            raise ValueError('Conda 未返回有效的 base 路径')
        if prefix.resolve() == base.resolve():
            raise ValueError('sc-wiki 指向 Conda base，拒绝安装项目依赖')
        version = run([prefix / 'bin/python', '-c', 'import sys; print("%d.%d" % sys.version_info[:2])'], capture=True).strip()
        if version != versions(root)['python']:
            raise ValueError(f'已有 sc-wiki Python {version} 不兼容；不会删除或重建环境')
    return conda, prefix


def runtime_prefix(root: Path) -> Path:
    record = root / '.local/deployment-environment.json'
    if record.is_file():
        prefix = Path(json.loads(record.read_text())['prefix'])
        if not (prefix / 'bin/python').is_file():
            raise ValueError('部署记录中的 Python 环境不存在')
        return prefix
    _, prefix = find_environment(root)
    if prefix is None:
        raise ValueError('缺少 sc-wiki 环境，请执行 make deploy')
    return prefix


def go_environment() -> dict[str, str]:
    """安装器与源码重载共用 Go 缓存/模块源，显式配置优先。"""
    defaults = {'GOPATH': str(Path.home() / '.local/gopath'),
                'GOCACHE': str(Path.home() / '.cache/go-build'),
                'GOPROXY': 'https://goproxy.cn,direct'}
    return {key: os.environ.get(key) or value for key, value in defaults.items()}


if __name__ == '__main__':
    import sys
    try:
        if sys.argv[2:] == ['--go-env']:
            for key, value in go_environment().items():
                sys.stdout.write(f'{key}={value}\0')
        else:
            print(runtime_prefix(Path(sys.argv[1])))
    except (ValueError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2)


def preflight(root: Path, *, occupied_ok=False) -> list[str]:
    problems = []
    if platform.system() != 'Linux' or platform.machine() not in ('x86_64', 'amd64'):
        problems.append('首版只支持 Linux x86_64 / WSL2 Ubuntu')
    for name in ('bash', 'make', 'curl', 'tar', 'setsid', 'ss'):
        if not shutil.which(name):
            problems.append(f'缺少系统前置工具 {name}')
    if not (root / 'scripts/local-deploy-versions.json').is_file():
        problems.append('目标不是包含部署脚本的完整源码目录')
    if not os.access(root, os.W_OK):
        problems.append('目标目录不可写')
    if not occupied_ok:
        for port in PORTS:
            with socket.socket() as sock:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                try:
                    sock.bind(('127.0.0.1', port))
                except OSError:
                    problems.append(f'端口 {port} 已被占用，不能复用未知服务')
    if shutil.disk_usage(root).free < 8 * 1024**3:
        problems.append('可用磁盘不足 8 GiB，无法准备依赖与临时数据')
    return problems


def download(item: dict, target: Path):
    if target.is_file() and digest(target) == item['sha256']:
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + '.partial')
    try:
        print(f'下载并校验本机依赖：{target.name}', flush=True)
        urls = [item['url'], *item.get('fallback_urls', [])]
        for index, url in enumerate(urls):
            try:
                run(['curl', '--fail', '--location', '--proto', '=https', '--connect-timeout', '20',
                     '--max-time', '1200', '--retry', '2', '--output', temporary, url])
                break
            except (ValueError, subprocess.TimeoutExpired) as exc:
                if index == len(urls) - 1:
                    raise ValueError(f'{target.name} 下载失败；请检查官方源的网络可达性，或将相同版本的官方文件放到 {target} 后重试（仍校验 SHA-256）') from exc
                print(f'{target.name} 主下载地址不可达，尝试版本清单内的备用地址', flush=True)
        if digest(temporary) != item['sha256']:
            raise ValueError('下载校验失败，拒绝执行安装文件')
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)


def extract_tool(archive: Path, target: Path):
    with tarfile.open(archive) as tar:
        tar.extractall(target, filter='data')


def install(root: Path) -> Path:
    spec = versions(root)
    local = root / '.local'
    cache = local / 'downloads'
    conda, prefix = find_environment(root)
    if conda is None:
        raise ValueError('缺少用户准备的 Conda；请先安装并设置 CONDA_EXE，脚本不会自动安装 Conda')
    if prefix is None:
        run([conda, 'create', '-y', '-n', 'sc-wiki', '--override-channels', '-c', 'conda-forge',
             *spec['conda_packages']])
        prefix = find_environment(root)[1]
    else:
        run([conda, 'install', '-y', '-p', prefix, '--override-channels', '-c', 'conda-forge',
             *spec['conda_packages']])
    if prefix is None:
        raise ValueError('sc-wiki 环境创建后无法定位')
    process_env = {**os.environ, **go_environment(), 'PYTHONNOUSERSITE': '1',
                   'PATH': f'{prefix}/bin:' + os.environ.get('PATH', '')}
    run([prefix / 'bin/python', '-m', 'pip', 'install', '-r', root / 'docker/requirements.txt'], env=process_env)
    run([prefix / 'bin/python', '-m', 'pip', 'check'], env=process_env)
    run([prefix / 'bin/python', '-c', 'import fastapi,pymysql,redis,rq,neo4j,qdrant_client,pymatgen,alembic,watchfiles'], env=process_env)
    run([prefix / 'bin/npm', 'ci'], cwd=root / 'frontend', env=process_env)
    for name in ('go', 'qdrant'):
        binary = local / ('go/bin/go' if name == 'go' else 'bin/qdrant')
        if binary.exists():
            actual = run([binary, 'version' if name == 'go' else '--version'], capture=True)
            if spec[name]['version'] not in actual:
                raise ValueError(f'已有 {name} 版本不兼容，不覆盖')
        else:
            archive = cache / (name + '.tar.gz')
            download(spec[name], archive)
            with tempfile.TemporaryDirectory(dir=local) as temporary:
                extract_tool(archive, Path(temporary))
                binary.parent.mkdir(parents=True, exist_ok=True)
                if name == 'go':
                    # parent mkdir 创建的空 go/bin 不包含用户文件。
                    binary.parent.rmdir()
                    binary.parent.parent.rmdir()
                    shutil.move(str(Path(temporary) / 'go'), local / 'go')
                else:
                    shutil.copy2(Path(temporary) / 'qdrant', binary)
    run([local / 'go/bin/go', 'mod', 'download'], cwd=root / 'goserver', env=process_env)
    run([local / 'go/bin/go', 'mod', 'verify'], cwd=root / 'goserver', env=process_env)
    from .native import install_neo4j, install_grobid
    install_neo4j(root, prefix, spec['neo4j'])
    install_grobid(root, conda, spec['grobid'])
    actual_packages = json.loads(run([conda, 'list', '-p', prefix, '--json'], capture=True))
    write_json(local / 'deployment-environment.json', {'prefix': str(prefix), 'conda': str(conda),
               'versions_digest': digest(root / 'scripts/local-deploy-versions.json'),
               'packages': [{k: row[k] for k in ('name', 'version', 'build_string')} for row in actual_packages]})
    return prefix

"""Neo4j 与 GROBID 的本机安装；所有制品只写入项目运行目录。"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import stat
import tempfile
import zipfile

from .bundle import write_json
from .environment import download, extract_tool, run


def install_neo4j(root: Path, prefix: Path, spec: dict):
    local = root / '.local'
    target = local / 'neo4j'
    env = {**os.environ, 'JAVA_HOME': str(prefix)}
    if not target.exists():
        archive = local / 'downloads/neo4j.tar.gz'
        download(spec, archive)
        with tempfile.TemporaryDirectory(prefix='neo4j-install-', dir=local) as temporary:
            extract_tool(archive, Path(temporary))
            prepared = Path(temporary) / ('neo4j-community-' + spec['version'])
            actual = run([prepared / 'bin/neo4j', '--version'], env=env, capture=True)
            if actual.strip() != spec['version']:
                raise ValueError('Neo4j 发行包版本不兼容')
            prepared.rename(target)
    actual = run([target / 'bin/neo4j', '--version'], env=env, capture=True)
    if actual.strip() != spec['version']:
        raise ValueError('已有 Neo4j 版本不兼容，不覆盖')


def extract_zip(archive: Path, target: Path):
    """Gradle ZIP 保留可执行位，同时拒绝路径越界和符号链接。"""
    with zipfile.ZipFile(archive) as bundle:
        for member in bundle.infolist():
            path = Path(member.filename)
            mode = member.external_attr >> 16
            if path.is_absolute() or '..' in path.parts or stat.S_ISLNK(mode):
                raise ValueError('安装包包含不安全路径')
            result = Path(bundle.extract(member, target))
            if mode and result.is_file():
                result.chmod(0o755 if mode & 0o111 else 0o644)


def configure_grobid(target: Path):
    config = target / 'grobid-home/config/grobid.yaml'
    text = config.read_text()
    for port in (8070, 8071):
        original = f'      port: {port}\n'
        if text.count(original) != 1:
            raise ValueError('GROBID 官方配置结构变化，拒绝生成未知监听配置')
        text = text.replace(original, original + '      bindHost: 127.0.0.1\n')
    config.write_text(text)


def verify_grobid(target: Path, spec: dict):
    for name in ('grobid-service/bin/grobid-service',
                 f'grobid-service/lib/grobid-core-{spec["version"]}.jar',
                 'grobid-home/config/grobid.yaml', 'grobid-home/models/citation/model.wapiti',
                 'grobid-home/lib/lin-64/libwapiti.so', 'grobid-home/pdfalto/lin-64/pdfalto'):
        if not (target / name).is_file():
            raise ValueError(f'GROBID 安装不完整：{name}')


def install_grobid(root: Path, conda: Path, spec: dict):
    local = root / '.local'
    local.mkdir(parents=True, exist_ok=True)
    target = local / 'grobid'
    java = local / 'grobid-java'
    marker = target / 'native-install.json'
    # 不根据单个启动文件猜测构建完成，也不覆盖用户放置的未知目录。
    if target.exists():
        if not marker.is_file() or json.loads(marker.read_text()) != spec:
            raise ValueError('已有 GROBID 安装来源或版本不兼容，不覆盖')
        verify_grobid(target, spec)
    if not (java / 'conda-meta/history').is_file():
        if java.exists():
            raise ValueError('GROBID Java 目录归属不明，不覆盖')
        run([conda, 'create', '-y', '-p', java, '--override-channels', '-c', 'conda-forge',
             *spec['conda_packages']])
    actual = run([java / 'bin/java', '--version'], capture=True)
    fields = actual.split()
    if len(fields) < 2 or fields[0] != 'openjdk' or fields[1].split('-')[0] != spec['java_version']:
        raise ValueError('GROBID Java 版本不兼容，不覆盖')
    if target.exists():
        return
    cache = local / 'downloads'
    source_archive, gradle_archive = cache / 'grobid.tar.gz', cache / 'gradle.zip'
    download(spec, source_archive)
    download(spec['gradle'], gradle_archive)
    env = {**os.environ, 'JAVA_HOME': str(java), 'GRADLE_USER_HOME': str(local / 'gradle-cache'),
           'PATH': f'{java}/bin:' + os.environ.get('PATH', '')}
    with tempfile.TemporaryDirectory(prefix='grobid-install-', dir=local) as temporary:
        stage = Path(temporary)
        extract_tool(source_archive, stage)
        extract_zip(gradle_archive, stage)
        source = stage / ('grobid-' + spec['version'])
        gradle = stage / ('gradle-' + spec['gradle']['version']) / 'bin/gradle'
        # 使用上游已配置重复依赖处理的 distZip，与官方发行构建保持一致。
        run([gradle, '--no-daemon', '--console=plain', ':grobid-service:distZip'],
            cwd=source, env=env, timeout=1800)
        prepared = stage / 'prepared'
        prepared.mkdir()
        service = 'grobid-service-' + spec['version']
        extract_zip(source / 'grobid-service/build/distributions' / (service + '.zip'), stage)
        shutil.move(stage / service, prepared / 'grobid-service')
        shutil.move(source / 'grobid-home', prepared / 'grobid-home')
        configure_grobid(prepared)
        verify_grobid(prepared, spec)
        (prepared / 'logs').mkdir()
        (prepared / 'grobid-home/tmp').mkdir(exist_ok=True)
        write_json(prepared / 'native-install.json', spec)
        prepared.rename(target)

"""可校验归档；拒绝路径逃逸及链接，先校验再解包。"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import tarfile
import uuid


def discover_archive(root: Path) -> Path | None:
    """只检查直接子项；多包不得根据时间、文件名或显式参数静默取舍。"""
    directory = root / 'dist'
    if directory.is_symlink() or (directory.exists() and not directory.is_dir()):
        raise ValueError('dist 必须为本项目的普通目录，不能是符号链接')
    if not directory.exists():
        return None
    suffixes = ('.tar', '.gz', '.tgz', '.bz2', '.tbz', '.tbz2', '.xz', '.txz',
                '.zst', '.tzst', '.zip', '.7z', '.rar')
    candidates = sorted(p for p in directory.iterdir() if p.name.lower().endswith(suffixes))
    if len(candidates) > 1:
        raise ValueError(f'dist 中发现 {len(candidates)} 个压缩包，必须只能保留一个数据库压缩包；'
                         '请移走多余压缩包后重试（.sha256 校验文件不计数）')
    if not candidates:
        return None
    archive = candidates[0]
    if archive.is_symlink() or not archive.is_file():
        raise ValueError('dist 中的数据库压缩包必须是普通文件，不能是目录或符号链接')
    return archive


def digest(path: Path) -> str:
    result = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(chunk)
    return result.hexdigest()


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    fd = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def safe_relative(value: str) -> PurePosixPath:
    path = PurePosixPath(value)
    if not value or path.is_absolute() or '..' in path.parts or '\\' in value or '\n' in value or '\x00' in value:
        raise ValueError('归档路径不安全')
    return path


def archive_members(tar):
    members, names = [], set()
    for member in tar:
        path = safe_relative(member.name)
        if path.parts[0] != 'sc-wiki' or member.name in names or not (member.isfile() or member.isdir()):
            raise ValueError('归档包含重复、越界或链接成员')
        names.add(member.name)
        members.append(member)
    return members


def extract_archive(archive: Path, target: Path) -> Path:
    if target.exists():
        raise ValueError('解包目标已存在')
    with tarfile.open(archive, 'r:*') as tar:
        members = archive_members(tar)
        size = sum(m.size for m in members)
        ancestor = target.parent
        while not ancestor.exists():
            ancestor = ancestor.parent
        if shutil.disk_usage(ancestor).free < size * 1.2:
            raise ValueError('解包磁盘空间不足')
        target.mkdir(parents=True)
        for member in members:
            destination = target / member.name
            if member.isdir():
                destination.mkdir(parents=True, exist_ok=True)
            else:
                destination.parent.mkdir(parents=True, exist_ok=True)
                with tar.extractfile(member) as src, destination.open('xb') as dst:
                    shutil.copyfileobj(src, dst)
                destination.chmod(0o700 if member.mode & 0o111 else 0o600)
    return target / 'sc-wiki'


def inventory(root: Path) -> dict:
    result = {}
    for path in sorted(root.rglob('*')):
        if path.is_symlink():
            raise ValueError('迁移包不允许符号链接')
        if path.is_file():
            relative = path.relative_to(root).as_posix()
            if relative in ('.deployment/manifest.json', '.deployment/checksums.sha256'):
                continue
            safe_relative(relative)
            result[relative] = {'size': path.stat().st_size, 'sha256': digest(path)}
    return result


def seal(root: Path, metadata: dict) -> dict:
    files = inventory(root)
    manifest = {**metadata, 'format_version': 1, 'bundle_id': str(uuid.uuid4()),
                'created_at': datetime.now(timezone.utc).isoformat(), 'files': files,
                'capacity': sum(item['size'] for item in files.values())}
    write_json(root / '.deployment/manifest.json', manifest)
    checksums = ''.join(f"{item['sha256']}  {name}\n" for name, item in files.items())
    (root / '.deployment/checksums.sha256').write_text(checksums, encoding='utf-8')
    return manifest


def verify(root: Path) -> dict:
    path = root / '.deployment/manifest.json'
    if path.is_symlink() or not path.is_file():
        raise ValueError('缺少迁移清单')
    manifest = json.loads(path.read_text())
    if (not isinstance(manifest, dict) or manifest.get('format_version') != 1
            or not isinstance(manifest.get('files'), dict)
            or not isinstance(manifest.get('bundle_id'), str)):
        raise ValueError('不支持的迁移包清单格式')
    uuid.UUID(manifest['bundle_id'])
    for name, expected in manifest['files'].items():
        safe_relative(name)
        file = root / name
        if file.is_symlink() or root.resolve() not in file.resolve().parents:
            raise ValueError('清单路径越界')
        if not file.is_file() or file.stat().st_size != expected['size'] or digest(file) != expected['sha256']:
            raise ValueError(f'文件校验失败：{name}')
    actual_payload = {p.relative_to(root).as_posix() for p in (root / '.deployment').rglob('*') if p.is_file()}
    expected_payload = {n for n in manifest['files'] if n.startswith('.deployment/')}
    if actual_payload != expected_payload | {'.deployment/manifest.json', '.deployment/checksums.sha256'}:
        raise ValueError('数据文件与清单不一致')
    expected_checksums = ''.join(f"{v['sha256']}  {k}\n" for k, v in manifest['files'].items())
    if (root / '.deployment/checksums.sha256').read_text() != expected_checksums:
        raise ValueError('校验清单不一致')
    return manifest


def publish(root: Path, destination: Path) -> None:
    checksum = destination.with_name(destination.name + '.sha256')
    if destination.exists() or checksum.exists():
        raise ValueError('输出文件已存在，拒绝覆盖')
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name('.' + destination.name + '.' + uuid.uuid4().hex)
    try:
        descriptor = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(descriptor, 'wb') as stream:
            with tarfile.open(fileobj=stream, mode='w:gz') as tar:
                tar.add(root, arcname='sc-wiki', recursive=True)
        # hard-link 发布不会覆盖在检查后由另一进程创建的文件。
        os.link(temporary, destination)
        with checksum.open('x', encoding='utf-8') as stream:
            stream.write(f'{digest(destination)}  {destination.name}\n')
    finally:
        temporary.unlink(missing_ok=True)

"""本机操作锁和恢复状态；绝不把已有数据视为可覆盖的临时目录。"""
from __future__ import annotations

from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import uuid

from .bundle import write_json


@contextmanager
def operation_lock(root: Path):
    directory = root / '.local'
    if directory.is_symlink() or (directory / 'deployment.lock').is_symlink():
        raise ValueError('操作目录或锁不能是符号链接')
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / 'deployment.lock').open('a') as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError('另一打包或部署操作正在执行') from None
        yield


class DeploymentState:
    def __init__(self, root: Path, record: dict):
        self.root, self.record = root, record
        self.path = root / '.local/deployment-state.json'
        self.staging = root / '.local' / ('restore-' + record['operation_id'])

    @classmethod
    def open(cls, root: Path, identity: str):
        result = cls.inspect(root, identity)
        result.save()
        return result

    @classmethod
    def inspect(cls, root: Path, identity: str):
        """预检与真正写入复用同一归属规则；本方法不创建任何文件。"""
        root = root.resolve()
        path = root / '.local/deployment-state.json'
        if path.exists():
            record = json.loads(path.read_text())
            if record.get('version') != 1 or record.get('identity') != identity or record.get('root') != str(root):
                raise ValueError('已有部署记录与目标或包不一致')
            uuid.UUID(record['operation_id'])
        else:
            if (root / '.data').exists() and any((root / '.data').iterdir()):
                raise ValueError('目标已有数据，拒绝覆盖；请在新目录部署')
            record = {'version': 1, 'identity': identity, 'root': str(root),
                      'operation_id': str(uuid.uuid4()), 'phase': 'preflight'}
        if (root / '.data').is_symlink() or (root / '.local').is_symlink():
            raise ValueError('目标运行目录不能是符号链接')
        result = cls(root, record)
        if (root / '.data').exists() and any((root / '.data').iterdir()) and not result.promoted:
            raise ValueError('目标已有不属于本操作的数据')
        return result

    @property
    def promoted(self) -> bool:
        marker = self.root / '.data/.deployment-owner.json'
        if not marker.is_file() or marker.is_symlink():
            return False
        return json.loads(marker.read_text()) == {'operation_id': self.record['operation_id'],
                                                  'identity': self.record['identity']}

    def save(self, phase: str | None = None, **updates):
        if phase:
            self.record['phase'] = phase
        self.record.update(updates)
        write_json(self.path, self.record)

    def promote(self):
        if self.promoted:
            return
        target = self.root / '.data'
        if target.exists():
            if any(target.iterdir()):
                raise ValueError('目标已有数据，拒绝覆盖')
            target.rmdir()
        write_json(self.staging / '.deployment-owner.json',
                   {'operation_id': self.record['operation_id'], 'identity': self.record['identity']})
        os.rename(self.staging, target)
        self.save('promoted')

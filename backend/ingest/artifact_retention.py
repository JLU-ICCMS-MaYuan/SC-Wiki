"""仅在仓库副本可经正常入口完整恢复后，移除本机已提交审核产物。"""
import hashlib
import json
from pathlib import Path
from backend.storage import create_storage
from backend.storage.paths import object_mode


def release_submitted_artifact(task_id, paper_id, paper_revision, *, local_path=None):
    from .upload_tasks import artifact_path, read_artifact_path, submitted_artifact_key
    result = {'deleted': False, 'bytes': 0}
    if not object_mode():
        return {**result, 'reason': 'local_storage'}
    path = Path(local_path) if local_path is not None else artifact_path(task_id)
    try:
        if path.is_symlink() or not path.is_file():
            return {**result, 'reason': 'no_local_file'}
        before = path.stat()
        raw = path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        expected = submitted_artifact_key(task_id, int(paper_id), int(paper_revision))
        reference = create_storage().describe(expected)
        if reference.size != len(raw) or reference.sha256 != digest:
            return {**result, 'reason': 'object_differs'}
        restored = read_artifact_path(task_id, paper_id=paper_id, paper_revision=paper_revision)
        restored_raw = restored.read_bytes()
        if len(restored_raw) != reference.size or hashlib.sha256(restored_raw).hexdigest() != reference.sha256:
            return {**result, 'reason': 'readback_differs'}
        value = json.loads(restored_raw)
        if (value.get('task_id'),value.get('paper_id'),value.get('paper_revision')) != (task_id,int(paper_id),int(paper_revision)):
            return {**result, 'reason': 'identity_differs'}
        after = path.stat()
        if (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns) != (
                after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns):
            return {**result, 'reason': 'local_changed'}
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            return {**result, 'reason': 'local_changed'}
        path.unlink()
        return {'deleted': True, 'bytes': len(raw), 'reason': 'verified_readback'}
    except Exception as error:
        # 清理不能让成功发布变成失败，更不能在验证失败时删除本机恢复副本。
        return {**result, 'reason': 'verification_failed', 'error_type': type(error).__name__}

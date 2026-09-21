"""仅迁移登记的文件字段，科学文本与指纹不参与字符串替换。"""
from __future__ import annotations

from pathlib import Path

PATH_FIELDS = {'file_path', 'stored_path', 'source_file_path', 'candidate_attachment',
               'pdf_path', 'markdown_path', 'artifact_path'}
FILE_DIRS = ('uploads', 'upload_PDFs', 'parsed_markdown', 'review_artifacts', 'clean_results', 'avatars')
FILE_NAMES = ('prop_name_ai_cache.json',)
JSON_COLUMNS = {
    'scientific_upload_drafts': ('draft', 'state'),
    'paper_revision_drafts': ('draft',),
}


def references(value, source: Path, pointer=''):
    result = []
    if isinstance(value, dict):
        for key, item in value.items():
            field_pointer = pointer + '/' + key.replace('~', '~0').replace('/', '~1')
            if key in PATH_FIELDS and isinstance(item, str) and item:
                path = Path(item)
                try:
                    relative = path.relative_to(source) if path.is_absolute() else path
                except ValueError:
                    raise ValueError('路径字段引用源数据根之外的文件') from None
                result.append({'field_pointer': field_pointer, 'source_root_id': 'data',
                               'relative_path': relative.as_posix()})
            else:
                result.extend(references(item, source, field_pointer))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            result.extend(references(item, source, pointer + '/' + str(index)))
    return result


def relocate(value, source: Path, target: Path, *, check_files: bool = False, field: str = ''):
    if isinstance(value, dict):
        return {k: relocate(v, source, target, check_files=check_files, field=k) for k, v in value.items()}
    if isinstance(value, list):
        return [relocate(v, source, target, check_files=check_files, field=field) for v in value]
    if field not in PATH_FIELDS or not isinstance(value, str) or not value:
        return value
    path = Path(value)
    try:
        relative = path.relative_to(source) if path.is_absolute() else path
    except ValueError:
        raise ValueError('发现数据目录之外的文件引用，请先登记迁移路径') from None
    if '..' in relative.parts or not relative.parts or relative.parts[0] not in FILE_DIRS:
        raise ValueError('文件引用不在允许的数据目录中')
    actual = source / relative
    if check_files and (not actual.is_file() or actual.is_symlink() or source.resolve() not in actual.resolve().parents):
        raise ValueError('被引用文件不存在或越界')
    return str(target / relative) if path.is_absolute() else value

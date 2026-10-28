"""保守识别上传文件身份；未知不制造冲突，提交不调用模型。"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata

RULE_VERSION = 'document-identity-v2'
_SI = re.compile(r'(?i)^(?:supporting|supplementary|supplemental)\s+(?:information|materials?|data)(?:\s+(?:for|to))?\s*[:：–—-]?\s*')
_SECTION = re.compile(r'(?i)^(?:abstract|significance|introduction|references|bibliography|methods|results|discussion|conclusions?|acknowledg\w*|author contributions|supporting information|supplementary information|research article|open access|contents|keywords|table of contents|computational methods)\b')
_DOI = re.compile(r'(?i)\b10\.\d{4,9}/[^\s<>"\]]+')
_AUTHOR = re.compile(r'[,;@]|\b(?:university|institute|department|laboratory)\b', re.I)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def normalized(value):
    value = unicodedata.normalize('NFKC', str(value)).casefold()
    value = re.sub(r'\\(?:mathrm|text|mathbf|mathit)\b', '', value)
    return ''.join(c for c in value if c.isalnum())


def _title(line):
    line = re.sub(r'^#{1,6}\s*', '', line).strip().strip('*').strip()
    if (not 20 <= len(line) <= 300 or len(line.split()) < 4 or _SECTION.match(line)
            or re.match(r'(?i)^(?:s?\d+[.)]\s|(?:fig(?:ure)?\.?|table|page|doi)\b|https?://)', line)
            or re.search(r'(?i)\b(?:vol\.|no\.\s*\d|\d+\s+of\s+\d+|doi.org|copyright)\b', line)
            or _DOI.search(line)):
        return None
    return line


def extract_identity(file_item, markdown):
    # 只读取首页；没有页标记时限于头部。正文引用中的 DOI 不能充当本论文 DOI。
    page = re.split(r'<!--\s*page:\s*(?:[2-9]|\d{2,})\s*-->', markdown, maxsplit=1)[0][:12000]
    lines = []
    for number, raw in enumerate(page.splitlines(), 1):
        text = raw.strip()
        if not text or text.startswith('<!--'):
            continue
        plain = re.sub(r'^#+\s*', '', text).strip()
        if re.fullmatch(r'(?i)(?:\d+[.)]?\s*)?(?:references|bibliography|参考文献)', plain):
            break
        lines.append((number, text, plain))
    title, evidence = None, {}
    for index, (number, text, plain) in enumerate(lines):
        si = _SI.match(plain)
        candidate = _title(_SI.sub('', plain)) if si else _title(plain)
        following = lines[index + 1:index + 4]
        prior_si = index > 0 and _SI.match(lines[index - 1][2])
        byline = bool(following and _AUTHOR.search(following[0][2]))
        heading = text.startswith('#')
        if candidate and (si or prior_si or (heading and byline) or (index < 5 and byline)):
            title = candidate
            evidence['title'] = {'line': number, 'quote': text}
            break
        # 多行标题：连接标题头及下一行，再由紧随的署名确认。
        if heading and candidate and len(following) >= 2 and not _AUTHOR.search(following[0][2]) and _AUTHOR.search(following[1][2]):
            joined = _title(candidate + ' ' + following[0][2])
            if joined and not _SECTION.match(following[0][2]):
                title = joined
                evidence['title'] = {'line': number, 'quote': text + '\n' + following[0][1]}
                break
    dois = {}
    for number, text, plain in lines:
        # 单独标识行或出版页眉页脚；拒绝含引用编号/叙述句子的任意段落 DOI。
        own_line = re.match(r'(?i)^(?:doi\s*:|https?://(?:dx\.)?doi.org/|www\.[^\s]+/doi/)', plain)
        publisher_line = bool(re.search(r'(?i)\b\d+\s+of\s+\d+\s*$', plain)
                              and not re.match(r'^\[?\d+[.)\]]', plain))
        if len(plain) <= 240 and (own_line or publisher_line):
            for match in _DOI.finditer(plain):
                value = match.group(0).rstrip('.,;)').casefold()
                dois[value] = {'line': number, 'quote': text}
    doi = next(iter(dois)) if len(dois) == 1 else None
    if doi:
        evidence['doi'] = dois[doi]
    return {'file_id': file_item.get('file_id'), 'filename': file_item.get('original_filename'),
            'role': file_item.get('role'), 'source_sha256': file_item.get('sha256'),
            'text_sha256': hashlib.sha256(markdown.encode()).hexdigest(),
            'title': title, 'doi': doi, 'authors': None, 'field_evidence': evidence}


def compare_identities(identities):
    mains = [item for item in identities if item.get('role') == 'main']
    conflicts, compared = [], []
    if len(mains) == 1:
        main = mains[0]
        for item in identities:
            if item is main:
                continue
            for field in ('doi', 'title', 'authors'):
                left, right = main.get(field), item.get(field)
                if not left or not right:
                    continue
                compared.append({'file_id': item.get('file_id'), 'field': field})
                def key(value):
                    if field == 'authors' and isinstance(value, list):
                        return sorted(normalized(v) for v in value)
                    return str(value).strip().casefold() if field == 'doi' else normalized(value)
                if key(left) != key(right):
                    conflicts.append({'field': field, 'main_file_id': main.get('file_id'),
                        'main_filename': main.get('filename'), 'file_id': item.get('file_id'),
                        'filename': item.get('filename'), 'main_value': left, 'file_value': right})
    return {'status': 'warning' if conflicts else 'ok' if compared else 'unknown',
            'conflicts': conflicts, 'compared_fields': compared, 'identities': identities,
            'rule_version': RULE_VERSION, 'source_version': digest(identities)}


def confirmation(state):
    check = state.get('consistency') or {}
    files = {f['file_id']: f.get('original_filename') or f['file_id'] for f in state.get('files') or []}
    lines = []
    for conflict in check.get('conflicts') or []:
        label = {'title': '标题', 'doi': 'DOI', 'authors': '作者'}.get(conflict.get('field'), '身份信息')
        main = conflict.get('main_filename') or files.get(conflict.get('main_file_id')) or '历史正文基准（未记录文件）'
        other = conflict.get('filename') or files.get(conflict.get('file_id')) or '对比文件'
        lines.append(f'{label}：\n{main}：{conflict.get("main_value")}\n{other}：{conflict.get("file_value")}')
    message = '上传文件的身份信息存在以下差异：\n\n' + '\n\n'.join(lines) if lines else '旧文件身份检查缺少具体差异记录，请核对这些文件是否属于同一篇论文。'
    version = digest([check, [(f.get('file_id'), f.get('role'), f.get('sha256')) for f in state.get('files') or []]])
    return message, version

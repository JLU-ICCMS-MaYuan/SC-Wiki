"""模型可调用的正式题录只读工具；不代替模型判断当前论文身份。"""
import re
from urllib.parse import quote

import httpx


def lookup(doi):
    doi = str(doi or '').strip().lower()
    if not re.fullmatch(r'10\.\d{4,9}/[^\s?#]+', doi):
        raise ValueError('需要从当前原文读取有效DOI')
    response = httpx.get('https://api.crossref.org/works/' + quote(doi, safe=''), timeout=15,
                         headers={'User-Agent': 'SC-Wiki bibliography verification'})
    response.raise_for_status()
    message = response.json()['message']
    if str(message.get('DOI', '')).lower() != doi:
        raise ValueError('正式题录返回的DOI不一致，不能采用')
    return {key: message.get(key) for key in
            ('DOI', 'title', 'container-title', 'volume', 'issue', 'page', 'article-number',
             'published', 'published-online', 'published-print')}

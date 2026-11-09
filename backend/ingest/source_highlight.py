"""在确定的来源块内定位原文；不增加模型调用或授予科学支持。"""
import hashlib
import re


def text_locator(content, quote):
    digest = hashlib.sha256(content.encode()).hexdigest()
    result = {'text_sha256': digest, 'char_interval': None, 'match_kind': 'unlocated'}
    if not quote.strip():
        return result
    def normalized(value):
        chars, positions = [], []
        for match in re.finditer(r'\S+|\s+', value):
            token = match.group()
            if token.isspace():
                chars.append(' '); positions.append((match.start(), match.end()))
            else:
                for offset, char in enumerate(token):
                    chars.append(char); positions.append((match.start() + offset, match.start() + offset + 1))
        return ''.join(chars), positions
    haystack, positions = normalized(content)
    needle, _ = normalized(quote.strip())
    starts = [m.start() for m in re.finditer(f'(?={re.escape(needle)})', haystack)]
    if len(starts) != 1:
        result['match_kind'] = 'ambiguous' if starts else 'unlocated'
        return result
    start = positions[starts[0]][0]; end = positions[starts[0] + len(needle) - 1][1]
    result.update(char_interval=[start, end], match_kind='exact' if content[start:end] == quote else 'whitespace_equivalent')
    return result


def source_reference(evidence, sources):
    """只把当前目录中可唯一定位的原句替换为引用，不靠数值猜来源。"""
    quote = evidence.get('quote')
    if not isinstance(quote, str) or not quote.strip():
        return None
    candidates = [s for s in sources if str(s.get('file_id')) == str(evidence.get('file_id'))
        and (not evidence.get('block_id') or evidence['block_id'] == s.get('block_id'))
        and (not evidence.get('source_sha256') or evidence['source_sha256'] == s.get('source_sha256'))]
    matches = [(s, text_locator(s['content'], quote)) for s in candidates]
    matches = [(s, span) for s, span in matches if span['char_interval'] is not None]
    if len(matches) != 1:
        return None
    source, span = matches[0]
    return {'source_id': source['source_id'], 'quote_span': span['char_interval']}

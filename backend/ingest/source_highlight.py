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

"""当前科学JSON的无损结构编码：共享重复节点，按列传输同形对象数组。"""
from __future__ import annotations

from collections import Counter
import hashlib
import json


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def encode_context(value):
    counts = Counter()

    def count(node):
        if isinstance(node, (dict, list, str)):
            text = _json(node)
            if len(text) >= 64:
                counts[text] += 1
        if isinstance(node, dict):
            for child in node.values():
                count(child)
        elif isinstance(node, list):
            for child in node:
                count(child)

    count(value)
    references, indices = [], {}

    def children(node):
        if isinstance(node, dict):
            result = {key: pack(child) for key, child in node.items()}
            return {'_object': result} if set(result) in ({'_ref'}, {'_rows'}, {'_object'}) else result
        if isinstance(node, list):
            rows = [pack(child) for child in node]
            if len(node) >= 2 and node[0] and all(isinstance(child, dict) and set(child) == set(node[0]) for child in node):
                columns = list(node[0])
                # 为行取字段时使用原对象的子节点，引用整行不改变列意义。
                table = {'_rows': {'columns': columns,
                    'values': [[pack(child[key]) for key in columns] for child in node]}}
                if len(_json(table)) < len(_json(rows)):
                    return table
            return rows
        return node

    def pack(node):
        if isinstance(node, (dict, list, str)):
            text = _json(node)
            if len(text) >= 64 and counts[text] > 1:
                if text not in indices:
                    index = len(references)
                    indices[text] = index
                    references.append(None)
                    references[index] = children(node)
                return {'_ref': indices[text]}
        return children(node)

    result = {'_context_encoding': 'lossless-tree-v1', 'data': pack(value), 'references': references,
              'sha256': hashlib.sha256(_json(value).encode()).hexdigest()}
    if decode_context(result) != value:
        raise ValueError('无损结构编码无法完整还原原始科学上下文')
    return result


def decode_context(encoded):
    if encoded.get('_context_encoding') != 'lossless-tree-v1':
        raise ValueError('未知上下文编码')
    references, cache, visiting = encoded['references'], {}, set()

    def expand(node):
        if isinstance(node, dict):
            if set(node) == {'_ref'}:
                index = node['_ref']
                if type(index) is not int or not 0 <= index < len(references) or index in visiting:
                    raise ValueError('上下文共享引用无效或循环')
                if index not in cache:
                    visiting.add(index)
                    cache[index] = expand(references[index])
                    visiting.remove(index)
                return cache[index]
            if set(node) == {'_object'}:
                return {key: expand(child) for key, child in node['_object'].items()}
            if set(node) == {'_rows'}:
                columns, rows = node['_rows']['columns'], node['_rows']['values']
                if len(set(columns)) != len(columns) or any(len(row) != len(columns) for row in rows):
                    raise ValueError('上下文列或行存在遗漏')
                return [{key: expand(child) for key, child in zip(columns, row)} for row in rows]
            return {key: expand(child) for key, child in node.items()}
        if isinstance(node, list):
            return [expand(child) for child in node]
        return node

    result = expand(encoded['data'])
    if hashlib.sha256(_json(result).encode()).hexdigest() != encoded['sha256']:
        raise ValueError('科学上下文完整性摘要不匹配')
    return result

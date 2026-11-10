"""真实结构失败请求重放；原文和历史保持，图片字节仅在测试夹具中省略。"""
import gzip
import json
from copy import deepcopy
from pathlib import Path

import pytest
from langchain_core.messages.utils import count_tokens_approximately

from backend.ingest import model_memory
from backend.ingest.structure_reading import compact_model_context, structure_tool_transport


def test_real_failed_request_fits_without_summarizing_or_removing_evidence(tmp_path, monkeypatch):
    fixture = json.loads(gzip.decompress((Path(__file__).parent /
        'fixtures/structure_budget/failed-request.json.gz').read_bytes()))
    original = fixture['request']
    original_bytes = json.dumps(original)
    # 原故障的摘要只能压旧页回执；最近结构报告和校验问题必须保留。
    monkeypatch.setattr(model_memory, 'compact_history', lambda history, *args, **kwargs:
        [{'role': 'user', 'content': '旧页读取过程摘要'}, *history[-2:]])
    with pytest.raises(model_memory.ContextBudgetError, match='压缩后必要上下文仍超限'):
        model_memory.prepare_request(original, tmp_path / 'before')
    request = deepcopy(original)
    request['tool_definitions'], restore = structure_tool_transport(request['tool_definitions'], fixture['catalog'])
    payload, history = compact_model_context(json.loads(request['user_prompt']), request['tool_history'])
    request.update(user_prompt=json.dumps(payload, ensure_ascii=False), tool_history=history)
    prepared = model_memory.prepare_request(request, tmp_path / 'after')
    assert prepared['tool_history'] == original['tool_history']
    assert prepared['images'] == original['images']
    assert json.loads(prepared['user_prompt'])['sources'] == json.loads(original['user_prompt'])['sources']
    assert json.loads(prepared['tool_history'][-1]['content']) == fixture['original_observation']
    assert model_memory._fixed_token_estimate(prepared) + count_tokens_approximately(
        model_memory._messages(prepared['tool_history'])) <= 96000
    for before, after in zip(original['tool_definitions'], prepared['tool_definitions']):
        block = before['function']['parameters'].get('properties', {}).get('block_id')
        if block and block.get('enum'):
            aliases = after['function']['parameters']['properties']['block_id']['enum']
            assert [restore(before['function']['name'], {'block_id': alias})['block_id']
                    for alias in aliases] == block['enum']
    assert json.dumps(original) == original_bytes

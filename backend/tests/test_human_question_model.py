from backend.ingest.model_review import review_fields


def records():
    return [{'key': key, 'item_key': key, 'field': 'material_name', 'current_value': 'YH10',
             'content_hash': key, 'source_hash': 'sources', 'state_key': key,
             'required': True} for key in ['conflict', 'neighbor']]


def test_real_conflict_is_reported_and_neighbor_finishes_in_same_budget():
    events = []
    def model(prompt, content, **options):
        import json
        request = json.loads(content)
        assert any(t['function']['name'] == 'request_human_question' for t in options['tool_definitions'])
        if not events:
            return {'action': {'name': 'request_human_question', 'arguments': {
                'key': 'conflict', 'reason_code': 'source_conflict', 'reason': '两个本文来源物相不同',
                'checked_context': '已经核对正文及附件', 'source_ids': [s['source_id'] for s in request['sources']],
                'recommendation': '采用附件物相并保留冲突'}}}
        assert [r['key'] for r in request['records']] == ['neighbor']
        return {'results': [{'key': 'neighbor', 'status': 'supported', 'resolution': 'resolved', 'reason': '原文明确',
                             'source_ids': [request['sources'][0]['source_id']]}]}
    def report(route, **kwargs):
        events.append(route)
        return {'question_id': 'q'}
    chunks = [{'file_id': 'main', 'chunk_index': 0, 'content': 'YH10 P63/mmc'},
              {'file_id': 'si', 'chunk_index': 1, 'content': 'YH10 Cc'}]
    result = review_fields(records(), chunks, model=model, on_human_question=report)
    assert events[0]['kind'] == 'human_required'
    assert result['conflict']['human_question_id'] == 'q'
    assert result['conflict']['status'] == 'unchecked' and not result['conflict'].get('review_error')
    assert result['neighbor']['status'] == 'supported'


def test_disabled_path_does_not_add_question_tool_or_model_calls():
    calls = []
    def model(prompt, content, **options):
        calls.append(content)
        assert all(t['function']['name'] != 'request_human_question' for t in options['tool_definitions'])
        return {'results': [{'key': r['key'], 'status': 'missing', 'reason': '未报告'} for r in records()]}
    assert len(review_fields(records(), [], model=model)) == 2
    assert len(calls) == 1


def test_explicit_final_conflict_is_queued_even_if_model_also_labels_it_supported():
    import json
    events = []
    def model(prompt, content, **options):
        request = json.loads(content)
        return {'results': [{'key': 'conflict', 'status': 'supported', 'resolution': 'human_required',
            'reason_code': 'source_conflict', 'reason': '表S1支持，但图注明确反驳，无法裁决',
            'source_ids': [s['source_id'] for s in request['sources']], 'checked_context': '已补读两处同压力原文',
            'recommendation': '采用结构表但保留冲突供人工决定'}]}
    def report(route, **kwargs):
        events.append(route); return {'question_id': 'q'}
    result = review_fields(records()[:1], [{'file_id': 'si', 'chunk_index': 0, 'content': 'Table S1: P63/mmc'},
        {'file_id': 'si', 'chunk_index': 1, 'content': 'Figure: Cmcm'}], model=model, on_human_question=report)
    assert len(events) == 1
    assert result['conflict']['status'] == 'unchecked' and result['conflict']['human_question_id'] == 'q'


def test_actual_conflicting_supported_excerpt_without_explicit_resolution_cannot_pass():
    import json
    from pathlib import Path
    fixture = json.loads((Path(__file__).parent/'fixtures/human-question-conflicting-supported.json').read_text())
    def model(prompt, content, **options):
        request = json.loads(content)
        # 固定回放只重绑测试目录身份，实际status/reason不改；不把摘录称为完整响应。
        return {'results': [{'key': 'conflict', 'status': fixture['status'], 'reason': fixture['reason'],
                            'source_ids': [s['source_id'] for s in request['sources']]}]}
    result = review_fields(records()[:1], [{'file_id': 'si', 'chunk_index': 0, 'content': 'fixture A'},
        {'file_id': 'si', 'chunk_index': 1, 'content': 'fixture B'}], model=model, max_rounds=1,
        on_human_question=lambda *_a, **_k: (_ for _ in ()).throw(AssertionError('缺少明确路由不能猜测发题')))
    assert result['conflict']['status'] == 'unchecked'
    assert 'resolution' in result['conflict']['review_error']

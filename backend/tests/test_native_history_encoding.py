from copy import deepcopy
from pathlib import Path
import json


def test_actual_native_receipt_survives_next_request_context_count_without_mutating_history(tmp_path):
    from backend.ingest.model_memory import prepare_request, _messages
    history=json.loads((Path(__file__).parent/'fixtures/native-history-extra-closer.json').read_text())
    before=deepcopy(history)
    expected,_=json.JSONDecoder().raw_decode(history[0]['tool_calls'][0]['function']['arguments'])
    def forbidden(*args,**kwargs):raise AssertionError('计数/编码不能额外调用模型')
    prepared=prepare_request({'system_prompt':'JSON fixed contract','user_prompt':'current source',
        'tool_history':history},tmp_path,model=forbidden,budget=96000)
    assert prepared['tool_history']==history==before
    message=_messages(history)[0]
    assert message.tool_calls[0]['args']==expected
    assert message.tool_calls[0]['id']==history[0]['tool_calls'][0]['id']

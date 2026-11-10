"""重放原503请求，仅补JSON指令；隔离验证真实接口，不执行业务保存或工具业务写入。"""
from dotenv import load_dotenv
load_dotenv('.env')
from pathlib import Path
from contextlib import nullcontext
import json,tarfile
from backend.rag.llm import complete_json,call_phase
from backend.rag.llm_context import catalog_config,set_llm_config,reset_llm_config
from backend.ingest.model_runtime import ModelRuntime,execution_context,atomic_json
from backend.rag.structured_output import validate_tool_action
ROOT=Path(__file__).resolve().parent;OUT=ROOT/'json-request-live';OUT.mkdir(exist_ok=True)
records=json.loads((ROOT/'json-mode-investigation.json').read_text());failed=max(records,key=lambda r:r['failures'])
with tarfile.open(ROOT/'previous-task-evidence.tar.gz') as archive:
 original=json.load(archive.extractfile(failed['request']))
request=original['request'];assert 'json' not in request['system_prompt'].lower()
config=catalog_config('LLM2');token=set_llm_config(config)
state={'status':'reading','execution_generation':1}
def write(**changes):state.update(changes);atomic_json(OUT/'state.json',state)
runtime=ModelRuntime('b7'*16,1,OUT/'runtime',lambda:dict(state),write,lambda:nullcontext(),
 identity={'provider':config.provider,'model':config.model})
try:
 with execution_context(runtime),call_phase('structure_reading'):
  result=complete_json(request['system_prompt'],request['user_prompt'],
   **{k:v for k,v in request.items() if k not in ('system_prompt','user_prompt')})
 validate_tool_action(result['action'],request['tool_definitions'])
 atomic_json(OUT/'result.json',result)
 summary={'model':config.model,'provider':config.provider,'source_request':failed['request'],
  'original_prompt_without_json':True,'only_json_instruction_added':True,
  'same_tool_definitions':True,'action':result['action']['name'],
  'native_tool_call':bool(result.get('_tool_call')),'scope':'真实单请求格式复验；不执行工具、不保存业务稿，非整篇解析或黑盒通过'}
 atomic_json(OUT/'summary.json',summary);print(json.dumps(summary,ensure_ascii=False),flush=True)
finally:reset_llm_config(token)

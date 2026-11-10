"""重发原失败分段的同模型/同输入；仅隔离请求与完整响应，不写业务稿。"""
from dotenv import load_dotenv
load_dotenv(".env")
from pathlib import Path
from contextlib import nullcontext
import json,hashlib
from backend.rag.llm import complete_json
from backend.rag.llm_context import catalog_config,set_llm_config,reset_llm_config
from backend.ingest.model_runtime import ModelRuntime,execution_context,atomic_json
ROOT=Path(__file__).parent;OUT=ROOT/"live";OUT.mkdir(exist_ok=True)
original=json.loads((ROOT/"original-call.json").read_text());p=Path(original["directory"])/"request.json";request=json.loads(p.read_text())["request"]
config=catalog_config("LLM2");token=set_llm_config(config);state={"status":"reading","execution_generation":1}
def write(**changes):state.update(changes);atomic_json(OUT/"state.json",state)
runtime=ModelRuntime("cd"*16,1,OUT/"runtime",lambda:dict(state),write,lambda:nullcontext(),identity={"provider":config.provider,"model":config.model})
try:
 with execution_context(runtime):
  response=complete_json(request["system_prompt"],request["user_prompt"],**{k:v for k,v in request.items() if k not in ["system_prompt","user_prompt"]})
 atomic_json(OUT/"response.json",response)
 reread=json.loads((OUT/"response.json").read_text());assert reread==response
 atomic_json(OUT/"summary.json",{"model":config.model,"provider":config.provider,"original_request_sha256":hashlib.sha256(p.read_bytes()).hexdigest(),"request_semantics":"与原失败相同的系统消息/输入/schema，不改变科学要求或补半截JSON","response_fields":list(response),"response_sha256":hashlib.sha256((OUT/"response.json").read_bytes()).hexdigest(),"scope":"真实原失败窗口新模型调用及严格schema/JSON保存重读；无业务写入，不是整篇或五阶段通过"})
 print(json.dumps({"status":"completed","fields":list(response)},ensure_ascii=False),flush=True)
finally:reset_llm_config(token)

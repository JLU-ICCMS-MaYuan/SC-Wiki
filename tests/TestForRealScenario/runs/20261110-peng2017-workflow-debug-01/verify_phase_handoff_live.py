"""沿已有原文交接和正式_read_chunk只重提误借声子物相的SI窗口，隔离写盘。"""
from dotenv import load_dotenv
load_dotenv(".env")
from pathlib import Path
from contextlib import nullcontext
import json,shutil,hashlib
from backend.ingest import upload_jobs as jobs
from backend.ingest.upload_tasks import artifact_directory,get_state
from backend.ingest.document_ir import DocumentIR
from backend.ingest.domain_extraction import structured_chunks
from backend.ingest.model_runtime import ModelRuntime,execution_context,atomic_json,digest
from backend.rag.llm_context import catalog_config,set_llm_config,reset_llm_config
from backend.storage import paths
ROOT=Path(__file__).parent/"issues/phase-handoff";OUT=ROOT/"live";OUT.mkdir(parents=True,exist_ok=True)
TASK="d789acceee124022b3257f84780d1156";FID="311d9c17cfa04095bcd3cb613872f4ce";FAKE="ef"*16
a=artifact_directory(TASK);business=get_state(TASK);case=json.loads((ROOT.parents[1]/"case.json").read_text());source=next(f for f in case["files"] if f["role"]=="supplementary")
assert hashlib.sha256(Path(source["path"]).read_bytes()).hexdigest()==source["sha256"]
art=OUT/"artifacts";(art/"document_ir").mkdir(parents=True,exist_ok=True);(art/"chunks"/FID).mkdir(parents=True,exist_ok=True)
for name in ["material_state_inventory_request.json","material_state_inventory.json"]:shutil.copy2(a/name,art/name)
shutil.copy2(a/"document_ir"/(FID+".json"),art/"document_ir"/(FID+".json"));shutil.copy2(a/"chunks"/FID/"00002.json",art/"chunks"/FID/"00002.json")
ir=DocumentIR.model_validate_json((art/"document_ir"/(FID+".json")).read_text());chunk=next(c for c in structured_chunks(ir) if c.chunk_index==2)
state={"task_id":FAKE,"status":"reading","execution_generation":1}
def write(**changes):state.update(changes);atomic_json(OUT/"state.json",state)
config=catalog_config("LLM2");assert digest(config.base_url)==business["execution_model"]["endpoint_hash"]
token=set_llm_config(config);runtime=ModelRuntime(FAKE,1,OUT/"runtime",lambda:dict(state),write,lambda:nullcontext(),identity={"provider":config.provider,"model":config.model})
# 仅隔离存储边界；正式读取、来源、类型、权限/代次与科学保护均不替换。
jobs.artifact_directory=lambda _:art
real_get=jobs.get_state;jobs.get_state=lambda task:dict(state) if task==FAKE else real_get(task)
paths.object_mode=lambda:False
try:
 with execution_context(runtime):result=jobs._read_chunk(FAKE,chunk,FID,{"file_id":FID,"kind":"pdf","parser_profile":"complementary","role":"supplementary","original_filename":Path(source["path"]).name,"stored_path":source["path"],"sha256":source["sha256"]})
 reread=json.loads((art/"chunks"/FID/"00002.json").read_text());assert reread==result
 ce=[s for s in result["material_states"] if s.get("material")=="CeH10"]
 summary={"model":config.model,"provider":config.provider,"source_sha256":source["sha256"],"source_resolution":result.get("_source_resolution"),"ceh10":ce,"scope":"同PDF真实原文交接、AI新提、正式normalize/校验及隔离候选保存重读；不写业务任务，不改跨物相保护"}
 atomic_json(OUT/"summary.json",summary)
 assert ce and all(s.get("reported_space_group_symbol") in [None,"","Fm-3m"] for s in ce)
 print(json.dumps({"ceh10_groups":[s.get("reported_space_group_symbol") for s in ce],"source_resolution":result.get("_source_resolution")},ensure_ascii=False),flush=True)
finally:reset_llm_config(token)

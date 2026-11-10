"""原PDF失败区域走正式反馈/标定/IR保存重读；全文和图片保持，隔离写盘。"""
from dotenv import load_dotenv
load_dotenv(".env")
from pathlib import Path
from contextlib import nullcontext
import json,hashlib,base64,io
import pymupdf
from PIL import Image
from backend.ingest.upload_tasks import artifact_directory,get_state
from backend.ingest.document_ir import DocumentIR
from backend.ingest.pdf_regions import render_region_image
from backend.ingest.image_feedback import read_chart
from backend.ingest.chart_reading import READING_PROMPT,_chart_image,calibrate_panel,append_readings
from backend.ingest.model_runtime import ModelRuntime,execution_context,atomic_json,digest
from backend.rag.llm_context import catalog_config,set_llm_config,reset_llm_config
from backend.rag.llm import complete_json,call_phase
ROOT=Path(__file__).parent;OUT=ROOT/"live";OUT.mkdir(exist_ok=True)
TASK="d789acceee124022b3257f84780d1156";FID="311d9c17cfa04095bcd3cb613872f4ce"
manifest=json.loads((ROOT/"catalog-probe.json").read_text())
original=json.loads((Path(manifest["failed_call"])/"request.json").read_text())["request"]
request=json.loads(original["user_prompt"])
for key in ["available_actions","available_regions","available_objects","region_id","image_receipt_version","feedback_version"]:
 request.pop(key,None)
case=json.loads((ROOT.parents[1]/"case.json").read_text());source=next(f for f in case["files"] if f["role"]=="supplementary");path=Path(source["path"])
assert hashlib.sha256(path.read_bytes()).hexdigest()==source["sha256"]==request["document"]["sha256"]
ir=DocumentIR.model_validate_json((artifact_directory(TASK)/"document_ir"/(FID+".json")).read_text())
context=render_region_image(path,request["complete_figure"])["png"]
with pymupdf.open(path) as pdf:
 crop,crop_png,origin=_chart_image(pdf,pdf[request["pdf_page"]-1],request["selected_regions"],request["crop_bbox"])
assert hashlib.sha256(crop_png).hexdigest()==request["crop_sha256"]
config=catalog_config("LLM2");assert digest(config.base_url)==get_state(TASK)["execution_model"]["endpoint_hash"]
token=set_llm_config(config);state={"status":"reading","execution_generation":1}
def write(**changes):state.update(changes);atomic_json(OUT/"state.json",state)
runtime=ModelRuntime("aa11"*8,1,OUT/"runtime",lambda:dict(state),write,lambda:nullcontext(),
 identity={"provider":config.provider,"model":config.model})
def event(value):
 atomic_json(OUT/("event-"+hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False).encode()).hexdigest()[:16]+".json"),value)
try:
 with execution_context(runtime),call_phase("chart_reading",filename=source["path"].split("/")[-1],pages=[request["pdf_page"]]):
  answer,revised,feedback=read_chart(complete_json,READING_PROMPT,request,
   ["data:image/png;base64,"+base64.b64encode(raw).decode() for raw in [context,crop_png]],
   ir,path,request["document"],crop,cancelled=lambda:False,on_event=event)
 with pymupdf.open(path) as pdf:crop,image_png,origin=_chart_image(pdf,pdf[request["pdf_page"]-1],request["selected_regions"],revised)
 image=Image.open(io.BytesIO(image_png));values=[];missing=[]
 for panel in answer["panels"]:
  v,m=calibrate_panel(panel,image,{**request["document"],"page":request["pdf_page"]},crop);values.extend(v);missing.extend(m)
 append_readings(ir,values);atomic_json(OUT/"ir.json",ir.model_dump(mode="json"));DocumentIR.model_validate_json((OUT/"ir.json").read_text())
 summary={"model":config.model,"provider":config.provider,"source_sha256":source["sha256"],"readings":values,"unresolved":missing,
 "notes":answer["notes"],"feedback":feedback,"scope":"原失败区域同源新模型、正式反馈/标定/IR保存重读；未改全文或图像、未写业务，非整篇/角色验收"}
 atomic_json(OUT/"summary.json",summary)
 assert values or missing or any(n["scope"]=="target" for n in answer["notes"])
 print(json.dumps({"values":len(values),"unresolved":len(missing),"notes":len(answer["notes"])},ensure_ascii=False),flush=True)
finally:reset_llm_config(token)

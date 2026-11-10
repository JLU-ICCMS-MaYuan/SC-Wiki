"""原PDF同一失败Tc面板重新请求原模型，正式标定、IR保存重读；只写隔离副本。"""
from dotenv import load_dotenv
load_dotenv(".env")
from pathlib import Path
from contextlib import nullcontext
import json,hashlib,base64,io
import pymupdf
from PIL import Image
from backend.rag.llm import complete_json
from backend.rag.llm_context import catalog_config,set_llm_config,reset_llm_config
from backend.ingest.model_runtime import ModelRuntime,execution_context,atomic_json
from backend.ingest.chart_reading import READING_PROMPT,VERSION,reading_schema,calibrate_panel,append_readings
from backend.ingest.pdf_regions import render_region_image
from backend.ingest.document_ir import DocumentIR
from backend.ingest.upload_tasks import artifact_directory
ROOT=Path(__file__).parent;OUT=ROOT/"live";OUT.mkdir(exist_ok=True)
request=json.loads((ROOT/"source.json").read_text());request["reader_version"]=VERSION
case=json.loads((ROOT.parents[1]/"case.json").read_text());source=next(f for f in case["files"] if f["role"]=="main")
path=Path(source["path"]);assert hashlib.sha256(path.read_bytes()).hexdigest()==request["document"]["sha256"]
context=render_region_image(path,request["complete_figure"])["png"]
with pymupdf.open(path) as pdf:
 crop=pdf[request["pdf_page"]-1].get_pixmap(dpi=600,alpha=False,clip=pymupdf.Rect(request["crop_bbox"])).tobytes("png")
assert hashlib.sha256(crop).hexdigest()==request["crop_sha256"]
image=Image.open(io.BytesIO(crop));assert list(image.size)==request["crop_image_size"]
# 当前源正文提供必要科学上下文，旧模型读数不作为原文输入。
with pymupdf.open(path) as pdf:request["source_pages"]=[{"page":4,"text":pdf[3].get_text()}]
config=catalog_config("LLM2");token=set_llm_config(config);state={"status":"reading","execution_generation":1}
def write(**changes):state.update(changes);atomic_json(OUT/"state.json",state)
runtime=ModelRuntime("ba"*16,1,OUT/"runtime",lambda:dict(state),write,lambda:nullcontext(),identity={"provider":config.provider,"model":config.model})
try:
 with execution_context(runtime):
  answer=complete_json(READING_PROMPT,json.dumps(request,ensure_ascii=False),images=["data:image/png;base64,"+base64.b64encode(v).decode() for v in [context,crop]],response_schema=reading_schema())
 atomic_json(OUT/"response.json",answer)
 values=[];missing=[]
 for panel in answer["panels"]:
  v,m=calibrate_panel(panel,image,{**request["document"],"page":4,"native_pixel_error":max(1000/image.width,1000/image.height)},request["crop_bbox"]);values.extend(v);missing.extend(m)
 ir=DocumentIR.model_validate_json((artifact_directory(case["task_id"])/"document_ir"/(request["document"]["file_id"]+".json")).read_text())
 for b in ir.blocks:
  if b.metadata.get("chart_reading",{}).get("quantity")=="tc":b.metadata.update(selected_for_reading=False,superseded_by=VERSION)
 append_readings(ir,values);atomic_json(OUT/"ir.json",ir.model_dump(mode="json"));reread=DocumentIR.model_validate_json((OUT/"ir.json").read_text())
 yh=[v for v in values if v["point"]["material"]=="YH10"]
 summary={"version":VERSION,"model":config.model,"provider":config.provider,"source_sha256":source["sha256"],"crop_sha256":request["crop_sha256"],"readings":len(values),"unresolved":missing,"yh10":yh,"values":values,"scope":"原PDF受影响Tc面板真实新请求、正式标定、IR保存重读；无业务写入"}
 atomic_json(OUT/"summary.json",summary)
 assert any(v["point"]["mu_star"]==.13 and 280<=v["value_number"]<=300 for v in yh),yh
 print(json.dumps({"readings":len(values),"unresolved":len(missing),"YH10":[(v["point"]["mu_star"],v["value_raw"],v["reading_precision"]) for v in yh]},ensure_ascii=False),flush=True)
finally:reset_llm_config(token)

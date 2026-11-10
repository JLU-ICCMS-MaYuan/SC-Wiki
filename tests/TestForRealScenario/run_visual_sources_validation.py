"""原PDF第4页的真实新调用；隔离ScH6后处理与内存存储，不写业务任务。"""
from pathlib import Path
import hashlib,json,os,re,sys,time
import argparse,base64
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
parser=argparse.ArgumentParser(description="原PDF局部新读图及正式后处理隔离验证，不写业务任务")
parser.add_argument("--pdf",type=Path,required=True)
parser.add_argument("--model",required=True,help="实际目录中的模型名，任务过程中固定")
parser.add_argument("--output",type=Path,required=True,help="新证据目录，禁止覆盖")
args=parser.parse_args()
from dotenv import load_dotenv
load_dotenv(ROOT/".env");os.environ["DATABASE_URL"]="sqlite:///:memory:"
import pymupdf
from backend.ingest.document_ir import DocumentIR,DocumentBlock,PageGeometry,content_hash
from backend.ingest.chart_reading import enrich_document
from backend.rag.llm import complete_json
from backend.rag.llm_context import catalog_config,set_llm_config,reset_llm_config
from backend.rag.llm_catalog import get_catalog

expected=args.model
identifier=next(x.id for x in get_catalog().items if x.model==expected)
config=catalog_config(identifier);set_llm_config(config)
OUT=args.output;OUT.mkdir(parents=True,exist_ok=False)
def save(name,value):(OUT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2,default=str))
counter=0
def model(prompt,content,**options):
    global counter
    counter+=1;number=counter;print('REQUEST',identifier,number,'images',len(options.get('images',[])),flush=True)
    save(f'call-{number}-input.json',{'prompt':prompt,'content':content,
        'schema':options.get('response_schema'),'tools':options.get('tool_definitions'),
        'image_count':len(options.get('images',[])),
        'image_sha256':[hashlib.sha256(base64.b64decode(url.split(',',1)[1])).hexdigest() for url in options.get('images',[])]})
    start=time.monotonic()
    options.setdefault('on_partial',lambda text:(OUT/f'call-{number}-partial.txt').write_text(text))
    result=complete_json(prompt,content,**options,_single_attempt=True,retries=0,read_timeout=90,
        on_call=lambda e:save(f'call-{number}-receipt.json',e))
    save(f'call-{number}-response.json',result)
    print('DONE',identifier,number,round(time.monotonic()-start,1),flush=True)
    return result

path=args.pdf.resolve();sha=hashlib.sha256(path.read_bytes()).hexdigest()
with pymupdf.open(path) as pdf:
    page=pdf[3];blocks=[]
    for i,item in enumerate(page.get_text('blocks')):
        if len(item)<5 or not isinstance(item[4],str):continue
        kind='caption' if re.match(r'^\s*(?:fig(?:ure)?\.?|table)\s*\d',item[4],re.I) else 'paragraph'
        blocks.append(DocumentBlock(block_id='original-4-'+str(i),block_type=kind,pdf_page=4,reading_order=i,
            text=item[4],bbox=tuple(item[:4]),content_hash=content_hash(item[4])))
    for image in page.get_image_info():
        blocks.append(DocumentBlock(block_id='native-4-'+str(len(blocks)),block_type='figure',pdf_page=4,
            reading_order=len(blocks),bbox=tuple(image['bbox']),content_hash=content_hash(image['bbox'])))
    ir=DocumentIR(document_id='visual-live',source_file_id='main',source_sha256=sha,parse_profile='complementary',
        parser={'name':'native-page-window','version':'1','mode':'text'},
        pages=[PageGeometry(pdf_page=4,width=page.rect.width,height=page.rect.height)],blocks=blocks)
save('provenance.json',{'model':config.model,'provider':config.provider,'source_sha256':sha,'pdf_page':4,
    'reused':'同一原PDF与未改变的文字层；不复用旧读图/科学提取/填写回答',
    'boundary':'原PDF局部新提取与正式后处理隔离验证；不写业务任务/草稿，不代表五阶段通过',
    'code_sha256':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ['backend/ingest/chart_reading.py','backend/ingest/pdf_regions.py','backend/ingest/image_reading.py','backend/ingest/image_feedback.py','backend/rag/llm.py']}})
try:
    report=enrich_document(ir,path,{'file_id':'main','sha256':sha,'filename':path.name,'role':'main'},model,
        on_event=lambda e:save('event-'+str(counter)+'-'+e['stage']+'-'+e['status']+'.json',e))
    save('chart-report.json',report);save('ir.json',ir.model_dump(mode='json'))
    restored=DocumentIR.model_validate_json((OUT/'ir.json').read_text())
    facts=[b.metadata['chart_reading'] for b in restored.blocks if b.metadata.get('chart_reading')]
    sc=[f for f in facts if f['point']['material'].replace(' ','').translate(str.maketrans('₀₁₂₃₄₅₆₇₈₉','0123456789'))=='ScH6']
    print('CHART',identifier,len(facts),'ScH6',[(f['quantity'],f['value_number']) for f in sc],flush=True)
    assert {f['quantity'] for f in sc}>={'tc','lambda_ep','dos_fermi'}
    from backend.ingest.domain_extraction import structured_chunks,COMPLEMENTARY_SYSTEM_PROMPT,EXTRACTION_OUTPUT_SCHEMA,normalize_extraction
    from backend.ingest.scientific_output_schema import bind_extraction_sources,decode_optional_containers,filling_schema
    from backend.ingest.state_optimization import assemble_candidates
    from backend.ingest.scientific_form_filling import fill_scientific_forms
    subset=restored.model_copy(deep=True)
    subset.blocks=[b for b in subset.blocks if 'chart_reading' not in b.metadata or b.metadata['chart_reading'] in sc]
    chunk=structured_chunks(subset)[0];context=json.loads(chunk.content)
    raw=model(COMPLEMENTARY_SYSTEM_PROMPT+'\nThis isolated regression extracts ONLY ScH6 records from supplied original source. Preserve every series and source.',
        chunk.content,response_schema=bind_extraction_sources(EXTRACTION_OUTPUT_SCHEMA,context,allow_block_references=True))
    allowed={(context['file_id'],b['pdf_page'],b['block_id']):b['text'] for p in context['pages'] for b in p['blocks']}
    extracted=normalize_extraction(decode_optional_containers(raw),allowed_blocks=set(allowed),allowed_tables={},
        allowed_pages={('main',4)},form_parameters=True,allowed_quote_text=allowed)
    save('extracted.json',extracted);states=assemble_candidates([extracted])
    def fill(prompt,content):return decode_optional_containers(model(prompt,content,response_schema=filling_schema()))
    values,filling=fill_scientific_forms(states,[{'file_id':'main','content':chunk.content,'file_role':'main','source_sha256':sha}],fill,
        on_attempt=lambda a:save('filling-attempt.json',a))
    save('filled.json',{'material_states':values,'report':filling});assert filling['status']=='completed'
    assert json.loads((OUT/'filled.json').read_text())['material_states']==values
    save('summary.json',{'status':'completed','model':config.model,'calls':counter,'readings':len(facts),
        'unresolved':len(report['unresolved']),'sc_readings':sc,'filling_status':filling['status'],'ir_reread':True,'form_reread':True})
except BaseException as error:
    save('summary.json',{'status':'incomplete','model':config.model,'calls':counter,'error_type':type(error).__name__,
        'status_code':getattr(error,'status_code',None),'boundary':'保留真实失败；没有改模型或业务数据'})
    print('INCOMPLETE',identifier,type(error).__name__,getattr(error,'status_code',None),flush=True)
    raise

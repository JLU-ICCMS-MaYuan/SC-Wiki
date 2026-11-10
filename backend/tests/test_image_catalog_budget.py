"""真实超限目录重放；整表替代重复入口，不能把旧AI观察伪装成当前原文。"""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import gzip,hashlib,json
import pymupdf
import pytest
from backend.ingest.document_ir import DocumentIR,DocumentBlock,PageGeometry,content_hash
from backend.ingest.review_tool_contract import tool_definitions

FIXTURE=Path(__file__).parent/"fixtures/image_catalog_budget/failed-request-and-catalog.json.gz"


def test_actual_feedback_call_fits_without_removing_science_or_images(tmp_path):
    from backend.ingest.image_feedback import read_chart
    from backend.ingest.pdf_regions import region_locator
    from backend.ingest.chart_reading import READING_PROMPT
    from backend.ingest.model_memory import prepare_fixed_request,_fixed_token_estimate
    with gzip.open(FIXTURE,"rt",encoding="utf-8") as f:data=json.load(f)
    path=tmp_path/"source.pdf"
    with pymupdf.open() as pdf:
        for _ in range(34):pdf.new_page(width=612,height=792)
        pdf[12].draw_rect((40,40,300,300),color=(0,0,0));pdf.save(path)
    sha=hashlib.sha256(path.read_bytes()).hexdigest()
    blocks=[DocumentBlock(**b,reading_order=i,content_hash=content_hash(b["text"])) for i,b in enumerate(data["blocks"])]
    ir=DocumentIR(document_id="catalog",source_file_id=data["source_file_id"],source_sha256=sha,
        parse_profile="complementary",pages=[PageGeometry(pdf_page=i+1,width=612,height=792) for i in range(34)],blocks=blocks)
    original=json.loads(data["request"]["user_prompt"])
    request=deepcopy(original);request["document"]["sha256"]=sha
    request["complete_figure"]=region_locator(path,ir.source_file_id,sha,13,[0,0,612,792])
    for key in ["available_objects","available_regions","available_actions"]:request.pop(key,None)
    pixels=["unchanged-context-pixels","unchanged-crop-pixels"]
    class Captured(Exception):pass
    def model(prompt,content,**options):
        actual=json.loads(content)
        assert actual["source_pages"]==original["source_pages"]
        assert options["images"]==pixels
        req={"system_prompt":prompt,"user_prompt":content,**options}
        prepared=prepare_fixed_request(req)
        assert _fixed_token_estimate(prepared)<96000
        assert len(actual["available_objects"])<300
        raise Captured
    with pytest.raises(Captured):
        read_chart(model,READING_PROMPT,request,pixels,ir,path,
            {"file_id":ir.source_file_id,"sha256":sha,"filename":"source.pdf","role":"supplementary"},
            request["crop_bbox"],cancelled=lambda:False,on_event=lambda _:None)


def block(key,kind="paragraph",box=(10,10,90,90),**kwargs):
    return DocumentBlock(block_id=key,block_type=kind,pdf_page=1,reading_order=0,
        bbox=box,text=key,content_hash=content_hash(key),**kwargs)


def test_visual_tool_schema_offers_complete_parent_not_retired_or_derived():
    parent=block("whole","table")
    cell=block("cell","table_cell",box=(20,20,30,30),parent_block_id="whole")
    orphan=block("orphan","table_cell",box=(120,120,130,130))
    retired=block("old",metadata={"selected_for_reading":False})
    derived=block("derived",metadata={"chart_reading":{"value_number":199}})
    ir=SimpleNamespace(blocks=[parent,cell,orphan,retired,derived],tables=[])
    tool=next(t for t in tool_definitions({"main":ir},[{"file_id":"main","kind":"pdf"}])
        if t["function"]["name"]=="read_complete_object")
    assert set(tool["function"]["parameters"]["properties"]["block_id"]["enum"])=={"whole","orphan"}


def test_context_and_ocr_do_not_turn_retired_ai_readings_into_original(tmp_path):
    from backend.tests.test_pdf_regions import source
    from backend.ingest.image_reading import ImageReadingTools
    path,ir=source(tmp_path)
    stale=block("RETIRED_WRONG_199",box=(40,50,80,80),
        metadata={"selected_for_reading":False,"source_kind":"vision","chart_reading":{}})
    derived=block("DERIVED_CURRENT_287",box=(40,50,80,80),
        metadata={"source_kind":"vision","chart_reading":{"value_number":287}})
    ocr=block("ORIGINAL_OCR",box=(40,50,80,80),metadata={"source_kind":"ocr"})
    ir.blocks.extend([stale,derived,ocr]);before=deepcopy(ir.blocks)
    tools=ImageReadingTools({"main":ir},{"main":path})
    full,_=tools.call("read_complete_object",{"file_id":"main","block_id":"fig"})
    receipt,_=tools.call("read_image_context",{"region_id":full["locator"]["region_id"]})
    text=json.dumps(receipt,ensure_ascii=False)
    assert "RETIRED_WRONG_199" not in text and "DERIVED_CURRENT_287" not in text
    assert "ORIGINAL_OCR" in text
    assert ir.blocks==before  # 历史/当前派生仍保存在IR，未删除来源。


def test_catalog_keeps_cell_without_accessible_or_containing_parent():
    from backend.ingest.image_catalog import visual_objects
    parent=block("parent","table")
    cell=block("contained","table_cell",box=(20,20,30,30),parent_block_id="parent")
    outside=block("outside","table_cell",box=(120,120,130,130),parent_block_id="parent")
    retired_parent=block("retired-table","table",metadata={"selected_for_reading":False})
    child=block("needs-own-entry","table_cell",parent_block_id="retired-table")
    ir=SimpleNamespace(blocks=[parent,cell,outside,retired_parent,child],tables=[])
    assert [b.block_id for b in visual_objects(ir)]==["parent","outside","needs-own-entry"]
    # 原IR只给table.cells关系时，同样能找到完整父表。
    cell.parent_block_id=None
    ir.tables=[SimpleNamespace(table_id="t",pdf_page=1,block_id="parent",
        cells=[SimpleNamespace(block_id="contained")])]
    assert [b.block_id for b in visual_objects(ir)]==["parent","outside","needs-own-entry"]


def test_legacy_cached_observations_are_preserved_but_not_reused_as_current(tmp_path):
    from backend.tests.test_pdf_regions import source
    from backend.ingest.image_reading import ImageReadingTools
    from backend.ingest.image_catalog import SOURCE_CONTEXT_VERSION
    path,ir=source(tmp_path);args={"file_id":"main","block_id":"fig"}
    tools=ImageReadingTools({"main":ir},{"main":path})
    good,_=tools.call("read_complete_object",args)
    legacy=deepcopy(good);legacy["receipt_id"]="legacy-receipt"
    legacy["reader"].pop("source_context_version",None)
    legacy["text_observations"].append({"text":"OLD_AI_VALUE_199"})
    saved=tools.state();saved["receipts"]={"legacy-receipt":legacy}
    saved["actions"]={content_hash("read_complete_object",args):"legacy-receipt"}
    restored=ImageReadingTools({"main":ir},{"main":path},state=saved)
    current,_=restored.call("read_complete_object",args)
    assert "OLD_AI_VALUE_199" not in json.dumps(current)
    assert current["reader"]["source_context_version"]==SOURCE_CONTEXT_VERSION
    assert restored.receipts["legacy-receipt"]==legacy

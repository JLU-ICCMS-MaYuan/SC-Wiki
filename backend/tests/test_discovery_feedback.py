"""前置盘点的真实几何错误应由原模型重读，保留原重复保护与已完成页。"""
from copy import deepcopy
import json
import pytest
from backend.tests.test_chart_reading import original,panel
from backend.ingest.chart_reading import enrich_document,page_inventory
from backend.ingest.chart_calibration import ChartReadingError


def duplicate():
    return {"pages":[{"page":1,"figures":[{"bbox":[100,100,900,900],"label":label,
        "target":True,"reason":"同一图外框被重复用于不同面板"}
        for label in ["Fig. 1 top","Fig. 1 middle","Fig. 1 bottom"]]}]}


def test_discovery_error_reenters_same_model_with_real_detail_and_reject_evidence(tmp_path):
    path,ir,source=original(tmp_path);calls=[];events=[];bad=duplicate()
    with pytest.raises(ChartReadingError):page_inventory(bad,{1:(200,200)})
    def model(prompt,content,**options):
        data=json.loads(content);calls.append((data,options))
        if "image_pages" in data:
            if len(calls)==1:return deepcopy(bad)
            assert data["image_pages"]==[1] and data["discovery_feedback"]["error"]
            assert data["discovery_feedback"]["geometry_issues"][0]["code"]=="DUPLICATE_PHYSICAL_REGION"
            assert data["discovery_feedback"]["geometry_issues"][0]["figure_indices"]==[0,1,2]
            assert options["images"][0]==calls[0][1]["images"][0]
            assert len(options["images"])==2
            assert data["additional_images"][0]["source_sha256"]==source["sha256"]
            return {"pages":[{"page":1,"figures":[{"bbox":[100,100,900,900],
                "label":"Fig. 1","target":True,"reason":"整图保留两个Tc系列"}]}]}
        return {"panels":[panel()],"notes":[]}
    report=enrich_document(ir,path,source,model,on_event=events.append)
    assert report["readings"]==2 and len(calls)==3
    assert any(e.get("stage")=="discovery_feedback" and e.get("response")==bad for e in events)


def test_same_invalid_discovery_has_no_unbounded_reasking_or_partial_success(tmp_path):
    path,ir,source=original(tmp_path);before=deepcopy(ir.blocks);calls=[]
    def model(prompt,content,**options):calls.append(1);return duplicate()
    with pytest.raises(ChartReadingError):enrich_document(ir,path,source,model)
    assert len(calls)==2 and ir.blocks==before


def test_structured_output_error_is_not_treated_as_a_geometry_repair(tmp_path):
    from backend.rag.structured_output import StructuredOutputError
    path,ir,source=original(tmp_path);calls=[]
    def model(*args,**kwargs):calls.append(1);raise StructuredOutputError("valid terminal but invalid schema")
    with pytest.raises(StructuredOutputError):enrich_document(ir,path,source,model)
    assert len(calls)==1


def test_successful_page_is_not_reinventoried_when_another_page_needs_repair(tmp_path):
    import hashlib,pymupdf
    from backend.ingest.document_ir import PageGeometry
    path,ir,source=original(tmp_path)
    two=tmp_path/"two.pdf"
    with pymupdf.open(path) as pdf:
        page=pdf.new_page(width=200,height=200);page.insert_text((20,30),"Structure drawing")
        pdf.save(two)
    sha=hashlib.sha256(two.read_bytes()).hexdigest();ir.source_sha256=sha
    ir.pages.append(PageGeometry(pdf_page=2,width=200,height=200));source["sha256"]=sha
    kept={"page":2,"figures":[{"bbox":[100,100,900,900],"label":"Fig. 2",
        "target":False,"reason":"非目标结构示意，保留实际排除理由"}]}
    requests=[]
    def model(prompt,content,**options):
        data=json.loads(content)
        if "image_pages" in data:
            requests.append(data["image_pages"])
            if len(requests)==1:
                result=duplicate();result["pages"].append(deepcopy(kept));return result
            return {"pages":[{"page":1,"figures":[{"bbox":[100,100,900,900],
                "label":"Fig. 1","target":True,"reason":"真实两个Tc系列"}]}]}
        return {"panels":[panel()],"notes":[]}
    report=enrich_document(ir,two,source,model)
    assert requests==[[1,2],[1]] and report["readings"]==2
    assert report["excluded"][0]["label"]=="Fig. 2"
    assert report["excluded"][0]["reason"]==kept["figures"][0]["reason"]

"""验证文件供应商适配的请求和不可信输出边界；不冒充真实供应商验收。"""
import json
from types import SimpleNamespace

import pytest
from backend.ingest.native_pdf import native_pdf_available, parse_native_pdf
from backend.ingest.document_parsers import DocumentSource, ParseOptions, ParserError


def test_pdf_support_is_explicit_and_not_inferred_from_compatible_api():
    config=SimpleNamespace(base_url="https://api.openai.com/v1",api_key="test-key",model="configured-pdf-model")
    assert native_pdf_available(config,["configured-pdf-model"])
    assert not native_pdf_available(config,[])
    config.base_url="https://compatible.example/v1"
    assert not native_pdf_available(config,["configured-pdf-model"])


@pytest.mark.parametrize("status,payload,valid", [
    ("completed",{"blocks":[{"pdf_page":1,"block_type":"paragraph","text":"200 K","bbox":[.1,.1,.5,.2]}]},True),
    ("incomplete",{"blocks":[]},False),
    ("completed",{"claims":[{"value":200}]},False),
    ("completed",{"blocks":[{"pdf_page":99,"block_type":"paragraph","text":"200 K","bbox":None}]},False),
])
def test_native_file_request_and_ir_validation(tmp_path,status,payload,valid):
    import pymupdf
    path=tmp_path/"paper.pdf"
    with pymupdf.open() as pdf:
        page=pdf.new_page();page.insert_text((40,80),"200 K");pdf.save(path)
    captured={}
    class Client:
        def __init__(self,**kwargs):
            self.responses=self;captured["config"]=kwargs
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def create(self,**kwargs):
            captured["request"]=kwargs
            return SimpleNamespace(status=status,output_text=json.dumps(payload),model="configured-pdf-model")
    config=SimpleNamespace(base_url="https://api.openai.com/v1",api_key="never-log-me",model="configured-pdf-model")
    def parse():
        return parse_native_pdf(DocumentSource(path,"file"),ParseOptions(profile="native_pdf_llm"),
            config=config,allowed_models=["configured-pdf-model"],client_factory=Client)
    if valid:
        ir=parse()
        assert ir.parser["mode"]=="vlm"
        assert ir.blocks[0].metadata["source_kind"]=="vision"
        assert ir.source_file_id=="file"
    else:
        with pytest.raises(ParserError) as error:parse()
        assert "never-log-me" not in str(error.value)
    request=captured["request"]
    assert request["store"] is False
    assert request["input"][0]["content"][0]["file_data"].startswith("data:application/pdf;base64,")
    assert "tools" not in request


def test_native_adapter_respects_explicit_runtime_capability(monkeypatch):
    from pathlib import Path
    from backend.ingest import native_pdf
    from backend.ingest.document_parsers import NativePdfLlmParser, RuntimeCapabilities
    monkeypatch.setattr(native_pdf,"native_pdf_available",lambda:True)
    source=DocumentSource(Path("unused.pdf"),"f")
    assert not NativePdfLlmParser().can_parse(source,RuntimeCapabilities(native_pdf_llm=False)).supported

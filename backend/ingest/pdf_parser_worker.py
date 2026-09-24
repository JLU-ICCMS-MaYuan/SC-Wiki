"""隔离重型解析库及模型生命周期，父进程负责超时和终止。"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def convert(request: dict) -> dict:
    source = Path(request["path"])
    options = request["options"]
    if request["parser"] == "docling":
        from docling.datamodel.base_models import InputFormat, ConversionStatus
        from docling.datamodel.pipeline_options import PdfPipelineOptions
        from docling.datamodel.accelerator_options import AcceleratorDevice, AcceleratorOptions
        from docling.document_converter import DocumentConverter, PdfFormatOption

        pipeline = PdfPipelineOptions(do_ocr=False, do_table_structure=True)
        pipeline.accelerator_options = AcceleratorOptions(device=AcceleratorDevice.CPU)
        pipeline.enable_remote_services = False
        converter = DocumentConverter(format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline)})
        result = converter.convert(source)
        if result.status != ConversionStatus.SUCCESS:
            raise ValueError("incomplete conversion")
        return {"document": result.document.export_to_dict(), "mode": "text"}
    if request["parser"] == "mineru":
        from mineru import parse
        from mineru.config import VlmConfig, config, LLMAidedConfig

        # 不继承宿主机的远端 LLM 配置；文献仅在当前子进程解析。
        config.llm_aided = LLMAidedConfig()
        tier = options.get("mineru_tier", "basic")
        mode = options.get("mineru_parse_mode", "ocr")
        result = parse(source, tier=tier, ocr_mode=mode, image_analysis=False,
                       vlm_config=VlmConfig(engine="llama-cpp", server_url=""))
        return {"document": result.to_dict(skip_defaults=False),
                "mode": "ocr" if mode == "ocr" else "text", "tier": tier}
    raise ValueError("unknown parser")


def main() -> None:
    request_path, response_path = map(Path, sys.argv[1:3])
    request = json.loads(request_path.read_text())
    try:
        payload = convert(request)
    except ImportError:
        payload = {"error": "parser_dependency_unavailable"}
    except (OSError, RuntimeError):
        payload = {"error": "parser_model_unavailable"}
    except Exception:
        payload = {"error": "parser_invalid_output"}
    response_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()

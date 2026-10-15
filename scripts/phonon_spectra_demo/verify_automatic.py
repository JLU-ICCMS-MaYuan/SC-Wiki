"""独立模型自动标定验收；不读取 cases/h3s-2014.json 的人工坐标。"""
from pathlib import Path
import argparse
import json
import sys
import numpy as np
from PIL import Image
import io

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from backend.spectra.discovery import pdf_figures, calibrate
from backend.spectra.engine import extract_panel


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--catalog-id",default="LLM2")
    args=parser.parse_args()
    from dotenv import dotenv_values
    import os
    for k,v in dotenv_values(".env").items():
        if v is not None:os.environ.setdefault(k,v)
    from backend.rag.llm_context import catalog_config,set_llm_config,reset_llm_config
    from backend.spectra.vision import verify_image_capability
    config=catalog_config(args.catalog_id);token=set_llm_config(config)
    states=[dict(state_key="r3m-130gpa",material="H3S",pressure_value_gpa=130,reported_space_group_symbol="R3m"),
            dict(state_key="im3m-200gpa",material="H3S",pressure_value_gpa=200,reported_space_group_symbol="Im-3m")]
    report=dict(model=config.model,manual_calibration_used=False,figures=[])
    args.output.mkdir(parents=True,exist_ok=True)
    try:
        try:
            report["vision_verified"]=verify_image_capability()
        except Exception as exc:
            report.update(vision_verified=False,error=type(exc).__name__,status="model_service_unavailable")
            (args.output/"automatic-report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2))
            return
        if report["vision_verified"]:
            for figure in pdf_figures(args.pdf):
                print("reading page",figure["pdf_page"],"image",figure["size_px"],flush=True)
                try:
                    panels,issues=calibrate(figure,states)
                except Exception as exc:
                    report["figures"].append(dict(source={k:v for k,v in figure.items() if k not in {"image","text"}},
                        panels=[],issues=[type(exc).__name__],results=[]))
                    (args.output/"automatic-report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2))
                    continue
                results=[extract_panel(np.asarray(Image.open(io.BytesIO(figure["image"])).convert("RGB")),p) for p in panels]
                report["figures"].append(dict(source={k:v for k,v in figure.items() if k not in {"image","text"}},
                    panels=panels,issues=issues,results=results))
                (args.output/("page-"+str(figure["pdf_page"])+".png")).write_bytes(figure["image"])
                (args.output/"automatic-report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False))
                print("panels",len(panels),"curves",sum(len(r["curves"]) for r in results),flush=True)
        else:
            print("selected model did not pass vision probe",flush=True)
        report["total_curves"]=sum(len(r["curves"]) for f in report["figures"] for r in f["results"])
        (args.output/"automatic-report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False))
    finally:reset_llm_config(token)


if __name__=="__main__":main()

"""同一 MinerU 全文输入下的 DeepSeek thinking 开关真实对照。"""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from statistics import mean

from .extraction import extract_arm
from .evaluate import evaluate_item
from .parsers import write_json
from backend.ingest.document_ir import DocumentIR
from backend.rag.llm_context import get_llm_config


def score(form, reference):
    candidate = form
    source = "validated_candidate"
    if not form.get("material_states") and isinstance(form.get("raw"), dict):
        raw = form["raw"]
        candidate = {"material_states": [s for s in raw.get("extraction", {}).get("material_states", []) if s.get("scope") == "current_paper"],
                     "structure_candidates": [{"reported_structure": x} for x in raw.get("structure_observations", [])]}
        source = "raw_candidate_contract_not_passed"
    rows = [{"id": item["id"], **evaluate_item(candidate, item)} for item in reference["items"]]
    return {"denominator": len(rows), "counts": dict(Counter(r["status"] for r in rows)), "scoring_source": source, "items": rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--repetitions", type=int, default=2)
    parser.add_argument("--max-tokens", type=int, default=65536)
    args = parser.parse_args()
    if args.repetitions < 1 or args.max_tokens < 1:
        parser.error("重复次数和 token 上限必须为正数")
    run = args.run_dir.resolve()
    manifest = json.loads((run / "manifest.json").read_text())
    reference = json.loads(args.reference.read_text())
    hashes = {f["file_id"]: hashlib.sha256(Path(f["path"]).read_bytes()).hexdigest() for f in manifest["case"]["files"]}
    if hashes != reference["source_sha256"] or hashes != {f["file_id"]: f["sha256"] for f in manifest["case"]["files"]}:
        raise ValueError("PDF 或参考清单身份不一致")
    originals = {("mineru", f["file_id"]): DocumentIR.model_validate_json((run / "mineru" / f["file_id"] / "ir.json").read_text())
                 for f in manifest["case"]["files"]}
    output = run / "reasoning-benchmarks" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output.mkdir(parents=True, exist_ok=False)
    print(f"BENCHMARK_DIR={output}", flush=True)
    config = get_llm_config()
    rows = []
    for repetition in range(1, args.repetitions + 1):
        order = [False, True] if repetition % 2 else [True, False]
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = []
            for thinking in order:
                mode = "on" if thinking else "off"
                trial = output / f"{mode}-{repetition}"
                options = {"thinking": thinking, "max_tokens": args.max_tokens, "reasoning_effort": "high"}
                futures.append((mode, trial, pool.submit(extract_arm, run, manifest, "mineru", config, originals,
                                                        output_root=trial, call_options=options)))
            for mode, trial, future in futures:
                form = future.result()
                call_path = trial / "extractions/mineru" / form["attempt"] / "call.json"
                call = json.loads(call_path.read_text()) if call_path.exists() else {}
                evaluation = score(form, reference)
                write_json(trial / "evaluation.json", evaluation)
                rows.append({"mode": mode, "repetition": repetition, "call": call, "validation": form["validation"],
                             "evaluation": evaluation, "trial": trial.name})
                write_json(output / "results.json", rows)
        print(f"Round {repetition} finished", flush=True)
    known = [r["call"] for r in rows if r["call"]]
    if len({c["input_sha256"] for c in known}) != 1 or len({c["system_prompt_sha256"] for c in known}) != 1:
        raise ValueError("对照输入或提示发生变化，不能汇总比较")
    summary = {}
    for mode in ("off", "on"):
        selected = [r for r in rows if r["mode"] == mode]
        summary[mode] = {"runs": len(selected), "completed": sum(r["call"].get("finish_reason") == "stop" for r in selected),
                         "mean_seconds": mean(r["call"]["elapsed_seconds"] for r in selected if r["call"]),
                         "correct_counts": [r["evaluation"]["counts"].get("correct", 0) for r in selected],
                         "record_contract_valid": [r["validation"].get("record_contract_valid", False) for r in selected]}
    write_json(output / "summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()

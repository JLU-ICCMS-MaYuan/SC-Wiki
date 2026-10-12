"""按 #125 固定样例调用真实模型，保存可复核结果，不自动给出人工评分。"""

from __future__ import annotations

import argparse
import ast
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import random
import re
import subprocess
import time
from types import SimpleNamespace

from backend.rag import service
from backend.rag.llm_client import get_llm_client
from backend.rag.llm_context import get_llm_config

ROOT = Path(__file__).resolve().parents[2]
BASELINE = "88e9676b38391fc93947583bca70e94580ab7bb0"
CASES = ROOT / "docs/specs/125-rag-chat-workspace/prompt-polish-evaluation.md"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="新建 JSON 文件；不覆盖已有结果")
    parser.add_argument("--repeat-from", type=Path, help="使用既有结果中 P01/P04/P10 的新版首轮输出检查重复润色")
    args = parser.parse_args()
    if args.output.exists():
        parser.error("结果文件已存在，请选用新路径以保留历史证据")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    cases = re.findall(r"^\| (P\d+) \| (.*?) \|", CASES.read_text(), re.M)
    if len(cases) != 12:
        raise RuntimeError("固定样例应为 12 条")
    source = subprocess.check_output(
        ["git", "show", f"{BASELINE}:backend/rag/service.py"], cwd=ROOT, text=True,
    )
    node = next(n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name == "polish_prompt")
    baseline_source = ast.get_source_segment(source, node)
    captured = []

    def observed_client(**kwargs):
        def create(**request):
            with get_llm_client(**kwargs) as client:
                response = client.chat.completions.create(**request)
            captured.append(response)
            return response
        return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))

    namespace = {"re": re, "get_llm_config": get_llm_config, "get_llm_client": observed_client,
                 "RagChatUnavailableError": service.RagChatUnavailableError}
    exec(compile(baseline_source, "<frozen-polish-baseline>", "exec"), namespace)
    service.get_llm_client = observed_client
    config = get_llm_config()
    jobs = [(round_no, case_id, draft, version) for round_no in (1, 2) for case_id, draft in cases
            for version in (("old", "new") if round_no == 1 else ("new", "old"))]
    if args.repeat_from:
        prior = json.loads(args.repeat_from.read_text())
        if prior["model"] != config.model:
            raise RuntimeError("重复润色必须使用同一模型")
        jobs = [(1, row["case"], row["suggestion"], "new") for row in prior["records"]
                if row["version"] == "new" and row["round"] == 1 and row["case"] in {"P01", "P04", "P10"}]
        if len(jobs) != 3:
            raise RuntimeError("重复润色所需的三个有效结果不完整")
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "model": config.model, "provider": config.provider,
        "baseline_commit": BASELINE, "baseline_source": baseline_source,
        "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "source_status": "工作区实现，尚未提交",
        "template_sha256": hashlib.sha256(service._POLISH_TEMPLATE.read_bytes()).hexdigest(),
        "template_text": service._POLISH_TEMPLATE.read_text(),
        "parameters": {"temperature": 0.2, "old_max_tokens": 400, "new_max_tokens": service.POLISH_MAX_TOKENS, "read_timeout": 30},
        "review_status": "待人工盲评", "records": [],
        "run_kind": "重复润色" if args.repeat_from else "新旧对比",
    }
    def save():
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    save()
    functions = {"old": namespace["polish_prompt"], "new": service.polish_prompt}
    # 两轮交换调用顺序，避免新版总是处于同一时间位置。
    for round_no, case_id, draft, version in jobs:
        captured.clear()
        start = time.perf_counter()
        record = {"case": case_id, "round": round_no, "version": version, "input": draft}
        try:
            record["suggestion"] = functions[version](draft)
            record["accepted"] = True
        except Exception as exc:
            record.update(accepted=False, error_type=type(exc).__name__)
        record["latency_seconds"] = round(time.perf_counter() - start, 3)
        if captured:
            response = captured[-1]
            choice = response.choices[0] if response.choices else None
            record.update(output=choice.message.content if choice else None,
                          finish_reason=choice.finish_reason if choice else None,
                          usage=response.usage.model_dump() if response.usage else None)
        report["records"].append(record)
        save()
        print(f'{len(report["records"])}/{len(jobs)} {case_id} round={round_no} {version} accepted={record["accepted"]}', flush=True)
    records = report["records"][:]
    random.Random(125).shuffle(records)
    report["blind_mapping"] = {f"B{i:02}": {"case": r["case"], "round": r["round"], "version": r["version"]}
                               for i, r in enumerate(records, 1)}
    blind = ["# 提示词润色匿名评审材料", "", "尚待人工评分；每项按目标清晰、内容完整、可执行性、适度与可读性各 0～2 分评审，并记录硬约束违规。", ""]
    for i, row in enumerate(records, 1):
        blind.extend([f'## B{i:02} · {row["case"]}', "", f'原文：{row["input"]}', "",
                      row.get("output") or "（无有效正文）", "", "评分与理由：待人工填写。", ""])
    args.output.with_suffix(".blind.md").write_text("\n".join(blind))
    save()


if __name__ == "__main__":
    main()

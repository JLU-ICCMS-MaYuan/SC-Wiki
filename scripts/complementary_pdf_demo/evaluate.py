"""独立评测入口；参考清单只在生成结束后读取，绝不传入模型。"""
from __future__ import annotations

import argparse
from collections import Counter
import json
import math
from pathlib import Path
import re

from .parsers import write_json
from .report import load_forms


def get_path(value, path):
    for part in path.split("/") if path else []:
        if isinstance(value, list):
            try:
                value = value[int(part)]
            except (IndexError, ValueError):
                return None
        elif isinstance(value, dict):
            value = value.get(part)
        else:
            return None
    return value


def candidates(form, query):
    kind = query["kind"]
    if kind.startswith("structure"):
        for structure in form.get("structure_candidates", []):
            observation = structure["reported_structure"]
            if observation.get("phase") == query["phase"] and observation.get("pressure_value_gpa") == query["pressure"]:
                yield get_path(observation, query["path"])
    else:
        for state in form.get("material_states", []):
            if state.get("reported_space_group_symbol") != query["phase"] or state.get("pressure_value_gpa") != query["pressure"]:
                continue
            for module in state.get("property_modules", []):
                for record in module.get("records", []):
                    if record.get("property_code") == query.get("property", "tc"):
                        yield ([record.get("value_min"), record.get("value_max")] if record.get("value_kind") == "range"
                               else record.get("value_number")) if query["path"] == "value" else get_path(record, query["path"])


def equivalent(value, expected, mode):
    if mode == "numbers":
        if isinstance(value, str):
            # 网格乘号及范围分隔仅用于明确参考项的比较，不回填生成结果。
            value = [float(s) for s in re.findall(r"\d+(?:\.\d+)?", value)]
        elif isinstance(value, (int, float)):
            value = [value]
        if not isinstance(value, list):
            return False
        expected = expected if isinstance(expected, list) else [expected]
        return len(value) == len(expected) and all(isinstance(v, (int, float)) and math.isclose(v, e, abs_tol=1e-6)
                                                   for v, e in zip(value, expected))
    if mode == "atom_coordinates":
        return isinstance(value, dict) and all(math.isclose(value.get(k, float("inf")), v, abs_tol=1e-6)
                                               for k, v in expected.items())
    if mode == "atom_label":
        return isinstance(value, dict) and value.get("label", value.get("atom", value.get("element"))) == expected
    if mode == "count":
        return isinstance(value, list) and len(value) == expected
    return value == expected


def evaluate_item(form, item):
    actual = [v for v in candidates(form, item["query"]) if v is not None]
    if not actual:
        # Tc 数值存在但挂在别的压力下，明确记错配而不是把它当无害遗漏。
        if item["query"]["kind"] == "record" and item["query"]["path"] == "value" and item["query"].get("property", "tc") == "tc":
            wrong = []
            for state in form.get("material_states", []):
                for module in state.get("property_modules", []):
                    for record in module.get("records", []):
                        if record.get("property_code") == "tc" and equivalent(record.get("value_number"), item["expected"], "numbers"):
                            wrong.append({"pressure": state.get("pressure_value_gpa"), "phase": state.get("reported_space_group_symbol"), "value": record.get("value_number")})
            if wrong:
                return {"status": "incorrect", "actual": wrong, "reason": "数值存在，但所属材料状态的压力/相不匹配参考原文"}
        return {"status": "missing", "actual": [], "reason": "未找到指定材料状态/结构下的字段"}
    status = "correct" if all(equivalent(v, item["expected"], item.get("mode", "exact")) for v in actual) else "incorrect"
    return {"status": status, "actual": actual, "reason": "与已目视核对的原文参考比较；不代表候选引句已全部合格"}


def evaluate(run, reference):
    manifest = json.loads((run / "manifest.json").read_text())
    actual_hashes = {f["file_id"]: f["sha256"] for f in manifest["case"]["files"]}
    if reference["source_sha256"] != actual_hashes:
        raise ValueError("参考清单与当前 PDF 身份不符")
    forms = load_forms(run)
    rows = [{**item, "results": {arm: evaluate_item(form, item) for arm, form in forms.items()}} for item in reference["items"]]
    counts = {arm: dict(Counter(row["results"][arm]["status"] for row in rows)) for arm in forms}
    changes = {}
    for arm in ("docling", "mineru", "marker"):
        changes[arm] = {"improved": [r["id"] for r in rows if r["results"][arm]["status"] != "correct" and r["results"]["complementary"]["status"] == "correct"],
                        "regressed": [r["id"] for r in rows if r["results"][arm]["status"] == "correct" and r["results"]["complementary"]["status"] != "correct"]}
    result = {"schema_version": 1, "run_id": manifest["run_id"], "scope": reference["scope"], "reference": reference["provenance"],
              "denominator": len(rows), "counts": counts, "changes": changes, "items": rows,
              "limitations": ["仅覆盖明确列出的核对项；不是全文或全表单准确率。", "来源定位质量另计，正确数值不等于证据合格。", "这是助手原图核对，不冒充用户最终验收。"]}
    write_json(run / "evaluation.json", result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--reference", type=Path, required=True)
    args = parser.parse_args()
    result = evaluate(args.run_dir, json.loads(args.reference.read_text()))
    print(json.dumps({k: result[k] for k in ("denominator", "counts", "changes")}, ensure_ascii=False, indent=2))

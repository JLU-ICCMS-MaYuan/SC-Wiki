"""离线比较同一人工标注集上的上传结果；不调用模型、不写业务数据库。"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import date
from decimal import Decimal
import hashlib
import json
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator


BENCHMARK_VERSION = "1"
CATEGORIES = frozenset({
    "digital", "scanned", "double_column", "multipage_table", "formula_dense",
    "figures_curves", "multi_pressure", "multi_material", "multi_method",
    "supplementary", "chinese", "english",
})
COMPLEX_CATEGORIES = frozenset({"scanned", "multipage_table", "multi_pressure"})
Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
Identifier = Annotated[str, Field(min_length=1, pattern=r"\S")]
Count = Annotated[int, Field(ge=0, strict=True)]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Region(Contract):
    file_sha256: Sha256
    pdf_page: int = Field(ge=1, strict=True)
    bbox: tuple[float, float, float, float]
    quote: Identifier

    @model_validator(mode="after")
    def geometry(self):
        x0, y0, x1, y1 = self.bbox
        if not (0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1):
            raise ValueError("评测区域必须是左上原点的 0～1 归一化非空矩形")
        return self


class Record(Contract):
    record_id: Identifier
    # 字段名、单位和枚举由导出契约统一，不在评分时做语义猜测。
    fields: dict[str, JsonValue] = Field(min_length=1)
    conditions: dict[str, JsonValue] = Field(default_factory=dict)
    evidences: list[Region] = Field(default_factory=list)


class Paper(Contract):
    paper_id: Identifier
    main_sha256: Sha256
    source_sha256s: list[Sha256] = Field(min_length=1)
    categories: list[str] = Field(min_length=1)
    annotator: Identifier
    reviewed_on: date
    records: list[Record] = Field(min_length=1)

    @model_validator(mode="after")
    def annotation(self):
        if not set(self.categories) <= CATEGORIES or len(set(self.categories)) != len(self.categories):
            raise ValueError("论文分类未知或重复")
        if self.main_sha256 not in self.source_sha256s or len(set(self.source_sha256s)) != len(self.source_sha256s):
            raise ValueError("主文件必须在不重复的来源清单内")
        _unique(self.records, "record_id")
        for record in self.records:
            if not record.evidences or any(e.file_sha256 not in self.source_sha256s for e in record.evidences):
                raise ValueError("人工标注必须引用清单内的文件区域")
        return self


class Corpus(Contract):
    schema_version: Literal["1"]
    kind: Literal["human", "synthetic"]
    papers: list[Paper] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_papers(self):
        _unique(self.papers, "paper_id")
        _unique(self.papers, "main_sha256")
        return self


class Resources(Contract):
    latency_seconds: float | None = Field(default=None, ge=0)
    input_tokens: Count | None = None
    output_tokens: Count | None = None
    cpu_seconds: float | None = Field(default=None, ge=0)
    gpu_seconds: float | None = Field(default=None, ge=0)
    cost_usd: float | None = Field(default=None, ge=0)
    human_edits: Count | None = None


class Prediction(Contract):
    paper_id: Identifier
    source_sha256s: list[Sha256] = Field(min_length=1)
    status: Literal["ready", "failed", "needs_review", "cancelled", "timeout"]
    records: list[Record] = Field(default_factory=list)
    resources: Resources = Field(default_factory=Resources)

    @model_validator(mode="after")
    def output(self):
        _unique(self.records, "record_id")
        if self.status != "ready" and self.records:
            raise ValueError("失败任务的部分候选不能作为已交付记录评分")
        if len(set(self.source_sha256s)) != len(self.source_sha256s):
            raise ValueError("预测来源清单重复")
        return self


class Run(Contract):
    schema_version: Literal["1"]
    run_id: Identifier
    pipeline_revision: Identifier
    parser_profile: Identifier
    model: Identifier
    papers: list[Prediction]

    @model_validator(mode="after")
    def unique_outputs(self):
        _unique(self.papers, "paper_id")
        return self


class AuditCheck(Contract):
    passed: bool = Field(strict=True)
    evidence: Identifier


class Checks(Contract):
    """由维护者填写的独立事务/恢复验收；不能从离线科学记录推断。"""
    failure_recovery: AuditCheck
    legacy_revision_review: AuditCheck
    unsupported_writes: Count
    writes_audit_evidence: Identifier


def _unique(items, field):
    values = [getattr(item, field) for item in items]
    if len(set(values)) != len(values):
        raise ValueError(f"重复身份：{field}")


def _canonical(value):
    # 数字字符串不等同数字，化学式大小写不合并，布尔值不等同 0/1。
    if isinstance(value, bool) or value is None:
        return (type(value).__name__, value)
    if isinstance(value, (float, int)):
        return ("number", str(Decimal(str(value)).normalize()))
    if isinstance(value, str):
        return ("text", " ".join(value.split()))
    if isinstance(value, list):
        return ("list", tuple(_canonical(item) for item in value))
    return ("object", tuple(sorted((key, _canonical(item)) for key, item in value.items())))


def _record_key(record, *, conditions=True):
    return (_canonical(record.fields), _canonical(record.conditions) if conditions else None)


def _region_matches(actual: Region, gold: Region) -> bool:
    if actual.file_sha256 != gold.file_sha256 or actual.pdf_page != gold.pdf_page:
        return False
    if " ".join(actual.quote.split()) != " ".join(gold.quote.split()):
        return False
    a, b = actual.bbox, gold.bbox
    intersection = max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1]))
    union = (a[2]-a[0])*(a[3]-a[1]) + (b[2]-b[0])*(b[3]-b[1]) - intersection
    return intersection / union >= 0.5


def _evidence_matches(actual: Record, gold: Record) -> bool:
    return bool(actual.evidences) and all(
        any(_region_matches(evidence, expected) for expected in gold.evidences)
        for evidence in actual.evidences
    )


def _located_count(actual: list[Record], gold: list[Record]) -> int:
    """二分图最大匹配：重复预测只计一次，顺序不能改变区域得分。"""
    edges = [[j for j, expected in enumerate(gold) if _evidence_matches(item, expected)] for item in actual]
    assigned = {}

    def assign(index, seen):
        for target in edges[index]:
            if target in seen:
                continue
            seen.add(target)
            if target not in assigned or assign(assigned[target], seen):
                assigned[target] = index
                return True
        return False

    return sum(assign(index, set()) for index in range(len(actual)))


def _metrics(counts):
    gold, predicted, correct = (counts[key] for key in ("gold", "predicted", "correct"))
    precision = correct / predicted if predicted else 0.0
    recall = correct / gold if gold else 0.0
    return dict(counts) | {
        "precision": precision, "recall": recall,
        "f1": 2 * correct / (gold + predicted) if gold + predicted else 0.0,
        "missed_record_rate": (gold-correct) / gold if gold else 0.0,
        "condition_accuracy": correct / counts["value_matches"] if counts["value_matches"] else 0.0,
        "evidence_location_rate": counts["located"] / predicted if predicted else 0.0,
    }


def _score(paper: Paper, prediction: Prediction | None):
    actual = prediction.records if prediction else []
    gold_groups, actual_groups = defaultdict(list), defaultdict(list)
    for item in paper.records:
        gold_groups[_record_key(item)].append(item)
    for item in actual:
        actual_groups[_record_key(item)].append(item)
    counts = {
        "gold": len(paper.records), "predicted": len(actual), "correct": 0, "located": 0,
        "value_matches": sum((Counter(_record_key(r, conditions=False) for r in paper.records)
                              & Counter(_record_key(r, conditions=False) for r in actual)).values()),
    }
    for key, expected in gold_groups.items():
        found = actual_groups[key]
        counts["correct"] += min(len(expected), len(found))
        counts["located"] += _located_count(found, expected)
    return counts


def _run_report(corpus: Corpus, run: Run):
    papers = {paper.paper_id: paper for paper in corpus.papers}
    predictions = {paper.paper_id: paper for paper in run.papers}
    if predictions.keys() - papers.keys():
        raise ValueError("预测包含不在固定评测清单中的论文")
    for key, prediction in predictions.items():
        if set(prediction.source_sha256s) != set(papers[key].source_sha256s):
            raise ValueError("预测与标注的来源文件摘要不一致")
    rows, totals, by_category, complex_counts = [], Counter(), defaultdict(Counter), Counter()
    for key, paper in papers.items():
        prediction = predictions.get(key)
        counts = _score(paper, prediction)
        totals.update(counts)
        for category in paper.categories:
            by_category[category].update(counts)
        if set(paper.categories) & COMPLEX_CATEGORIES:
            complex_counts.update(counts)  # 同一论文只加入复杂总计一次。
        rows.append({"paper_id": key, "status": prediction.status if prediction else "missing",
                     "main_sha256": paper.main_sha256, "source_sha256s": paper.source_sha256s,
                     "categories": paper.categories,
                     "resources": prediction.resources.model_dump() if prediction else None,
                     **_metrics(counts)})
    resources = {}
    for key in Resources.model_fields:
        values = [getattr(item.resources, key) for item in run.papers if getattr(item.resources, key) is not None]
        resources[key] = {"measured_papers": len(values), "total": sum(values) if values else None}
    return {
        "run_id": run.run_id, "pipeline_revision": run.pipeline_revision,
        "parser_profile": run.parser_profile, "model": run.model,
        "total": _metrics(totals), "complex": _metrics(complex_counts) if complex_counts else None,
        "by_category": {key: _metrics(value) for key, value in sorted(by_category.items())},
        "papers": rows, "resources": resources,
        "missing_papers": sorted(papers.keys() - predictions.keys()),
    }


def _digest(model):
    data = json.dumps(model.model_dump(mode="json"), sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(data.encode()).hexdigest()


def evaluate(corpus: Corpus, legacy: Run, new: Run, checks: Checks) -> dict:
    baseline, candidate = _run_report(corpus, legacy), _run_report(corpus, new)
    category_counts = Counter(category for paper in corpus.papers for category in paper.categories)
    report = {
        "benchmark_version": BENCHMARK_VERSION, "corpus_kind": corpus.kind,
        "corpus_sha256": _digest(corpus), "legacy_sha256": _digest(legacy), "new_sha256": _digest(new),
        "checks_sha256": _digest(checks), "checks": checks.model_dump(mode="json"),
        "annotated_papers": len(corpus.papers) if corpus.kind == "human" else 0,
        "category_papers": dict(sorted(category_counts.items())),
        "new_f1": candidate["total"]["f1"], "legacy_f1": baseline["total"]["f1"],
        "new_complex_recall": (candidate["complex"] or {}).get("recall", 0),
        "legacy_complex_recall": (baseline["complex"] or {}).get("recall", 0),
        "evidence_location_rate": candidate["total"]["evidence_location_rate"],
        "unsupported_writes": checks.unsupported_writes,
        "failure_recovery_passed": checks.failure_recovery.passed,
        "legacy_revision_review_passed": checks.legacy_revision_review.passed,
        "runs": {"legacy": baseline, "new": candidate},
    }
    from .parser_rollout import quality_gate_passed
    report["quality_gate_passed"] = quality_gate_passed(report)
    return report


def detailed_gate_passed(report: dict) -> bool:
    """质量门必须可回溯到完整的逐论文计数；摘要不能掩盖缺项和类别退步。"""
    if report.get("benchmark_version") != BENCHMARK_VERSION or report.get("corpus_kind") != "human":
        return False
    try:
        checks = Checks.model_validate(report["checks"])
        if (checks.unsupported_writes != report["unsupported_writes"]
                or checks.failure_recovery.passed != report["failure_recovery_passed"]
                or checks.legacy_revision_review.passed != report["legacy_revision_review_passed"]):
            return False
        for name in ("corpus", "legacy", "new", "checks"):
            digest = report[f"{name}_sha256"]
            if not isinstance(digest, str) or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
                return False
        if report["checks_sha256"] != _digest(checks):
            return False
        paper_categories = []
        for name in ("legacy", "new"):
            run = report["runs"][name]
            if run["missing_papers"] or len(run["papers"]) != report["annotated_papers"]:
                return False
            identities, totals, category_totals, complex_counts = {}, Counter(), defaultdict(Counter), Counter()
            main_hashes = set()
            for row in run["papers"]:
                key, categories = row["paper_id"], row["categories"]
                if not isinstance(key, str) or not key.strip() or key in identities:
                    return False
                if not categories or len(set(categories)) != len(categories) or not set(categories) <= CATEGORIES:
                    return False
                main_hash, sources = row["main_sha256"], row["source_sha256s"]
                if (main_hash not in sources or main_hash in main_hashes or len(set(sources)) != len(sources)
                        or any(not isinstance(value, str) or len(value) != 64
                               or any(c not in "0123456789abcdef" for c in value) for value in sources)):
                    return False
                main_hashes.add(main_hash)
                identities[key] = {"categories": sorted(categories), "main_sha256": main_hash,
                                   "source_sha256s": sorted(sources)}
                counts = {k: row[k] for k in ("gold", "predicted", "correct", "located", "value_matches")}
                if any(type(value) is not int or value < 0 for value in counts.values()):
                    return False
                if not (0 < counts["gold"] and counts["located"] <= counts["correct"] <= counts["value_matches"]
                        <= min(counts["predicted"], counts["gold"])):
                    return False
                if row["status"] not in {"ready", "failed", "needs_review", "cancelled", "timeout"}:
                    return False
                if row["status"] != "ready" and counts["predicted"]:
                    return False
                if any(row.get(k) != value for k, value in _metrics(counts).items()):
                    return False
                totals.update(counts)
                for category in categories:
                    category_totals[category].update(counts)
                if set(categories) & COMPLEX_CATEGORIES:
                    complex_counts.update(counts)
            if run["total"] != _metrics(totals) or not complex_counts or run["complex"] != _metrics(complex_counts):
                return False
            if run["by_category"] != {key: _metrics(counts) for key, counts in category_totals.items()}:
                return False
            category_counts = Counter(category for values in identities.values() for category in values["categories"])
            if set(category_counts) != CATEGORIES or report["category_papers"] != dict(category_counts):
                return False
            if report[f"{name}_f1"] != run["total"]["f1"] or report[f"{name}_complex_recall"] != run["complex"]["recall"]:
                return False
            paper_categories.append(identities)
        if paper_categories[0] != paper_categories[1]:
            return False
        old, new = report["runs"]["legacy"], report["runs"]["new"]
        return (report["evidence_location_rate"] == new["total"]["evidence_location_rate"]
                and all(new["by_category"][key]["recall"] > old["by_category"][key]["recall"]
                        for key in COMPLEX_CATEGORIES))
    except (KeyError, TypeError, ValueError, AttributeError):
        return False


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("corpus", "legacy", "new", "checks", "output"):
        parser.add_argument(f"--{name}", required=True, type=Path)
    args = parser.parse_args(argv)
    inputs = [args.corpus, args.legacy, args.new, args.checks]
    if args.output.resolve() in {path.resolve() for path in inputs}:
        parser.error("报告不能覆盖标注或输入结果")
    try:
        models = [schema.model_validate_json(path.read_text(encoding="utf-8"))
                  for schema, path in zip((Corpus, Run, Run, Checks), inputs)]
        report = evaluate(*models)
    except (ValueError, OSError) as error:
        parser.error(str(error))
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"report": str(args.output), "quality_gate_passed": report["quality_gate_passed"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""评测器反例：合成数据只验证算法，不作为逐篇人工核对证据。"""
import copy
import json
import subprocess
import sys

import pytest
from pydantic import ValidationError

from backend.ingest.pdf_benchmark import (
    CATEGORIES, Checks, Corpus, Region, Run, evaluate,
)
from backend.ingest.parser_rollout import RolloutConfig, RolloutStage, quality_gate_passed


def inputs(count=1, kind="synthetic"):
    papers, legacy, new = [], [], []
    for index in range(count):
        digest = f"{index:064x}"
        record = {"record_id": "r1", "fields": {"material": "LaH10", "tc_k": 200, "method": "resistivity"},
                  "conditions": {"pressure_gpa": 150},
                  "evidences": [{"file_sha256": digest, "pdf_page": 1, "bbox": [.1, .1, .5, .2], "quote": "Tc = 200 K"}]}
        papers.append({"paper_id": str(index), "main_sha256": digest, "source_sha256s": [digest],
                       "categories": sorted(CATEGORIES), "annotator": "test-only", "reviewed_on": "2026-09-24",
                       "records": [record]})
        legacy.append({"paper_id": str(index), "source_sha256s": [digest], "status": "failed"})
        new.append({"paper_id": str(index), "source_sha256s": [digest], "status": "ready", "records": [copy.deepcopy(record)]})
    meta = {"schema_version": "1", "run_id": "unit-test", "pipeline_revision": "fixture", "model": "mock"}
    return (
        {"schema_version": "1", "kind": kind, "papers": papers},
        meta | {"parser_profile": "legacy", "papers": legacy},
        meta | {"parser_profile": "text", "papers": new},
        {"failure_recovery": {"passed": True, "evidence": "unit-test-only"},
         "legacy_revision_review": {"passed": True, "evidence": "unit-test-only"},
         "unsupported_writes": 0, "writes_audit_evidence": "unit-test-only"},
    )


def score(raw):
    return evaluate(*(schema.model_validate(data) for schema, data in zip((Corpus, Run, Run, Checks), raw)))


def test_one_reviewed_paper_can_open_gate_but_synthetic_cannot():
    report = score(inputs())
    assert report["new_f1"] == 1
    assert report["annotated_papers"] == 0
    assert not quality_gate_passed(report)
    # 单篇人工核对即可参与质量门；配置切换仍由维护者显式执行。
    raw = inputs(1, "human")
    raw[0]["papers"][0]["categories"] = ["digital", "english"]
    report = score(raw)
    assert report["annotated_papers"] == 1
    assert report["runs"]["new"]["complex"] is None
    assert quality_gate_passed(report)
    assert RolloutConfig(stage=RolloutStage.DEFAULT, quality_report=report)


def test_missing_and_failed_papers_remain_in_denominator():
    raw = inputs(3)
    raw[2]["papers"].pop()
    raw[2]["papers"][1].update(status="timeout", records=[])
    report = score(raw)
    result = report["runs"]["new"]
    assert result["total"]["recall"] == pytest.approx(1/3)
    assert result["total"]["f1"] == .5
    assert result["missing_papers"] == ["2"]
    assert result["papers"][2]["status"] == "missing"
    assert result["resources"]["cost_usd"] == {"measured_papers": 0, "total": None}


def test_duplicate_predictions_are_false_positives_and_not_extra_locations():
    raw = inputs()
    record = copy.deepcopy(raw[2]["papers"][0]["records"][0])
    record["record_id"] = "duplicate"
    raw[2]["papers"][0]["records"].append(record)
    result = score(raw)["runs"]["new"]["total"]
    assert result["precision"] == .5
    assert result["recall"] == 1
    assert result["evidence_location_rate"] == .5


def test_wrong_condition_is_not_a_correct_record():
    raw = inputs()
    raw[2]["papers"][0]["records"][0]["conditions"]["pressure_gpa"] = 160
    result = score(raw)["runs"]["new"]["total"]
    assert result["value_matches"] == 1
    assert result["condition_accuracy"] == 0
    assert result["f1"] == 0


@pytest.mark.parametrize("change", [
    {"file_sha256": "f"*64}, {"pdf_page": 2}, {"bbox": [0, 0, 1, 1]}, {"quote": "Tc = 999 K"},
])
def test_wrong_evidence_fails_even_when_scientific_value_matches(change):
    raw = inputs()
    raw[2]["papers"][0]["records"][0]["evidences"][0].update(change)
    report = score(raw)
    assert report["new_f1"] == 1
    assert report["evidence_location_rate"] == 0


def test_numeric_precision_and_whitespace_normalization_preserve_semantics():
    raw = inputs()
    record = raw[2]["papers"][0]["records"][0]
    record["fields"].update(tc_k=200.0, material="  LaH10 ")
    assert score(raw)["new_f1"] == 1
    record["fields"]["tc_k"] = "200"
    assert score(raw)["new_f1"] == 0
    record["fields"]["tc_k"] = True
    assert score(raw)["new_f1"] == 0


def test_maximum_matching_is_independent_of_record_order():
    raw = inputs()
    paper, prediction = raw[0]["papers"][0], raw[2]["papers"][0]
    original = paper["records"][0]
    a, b = copy.deepcopy(original["evidences"][0]), copy.deepcopy(original["evidences"][0])
    b["bbox"] = [.1, .7, .5, .8]
    paper["records"] = [original | {"evidences": [a, b]}, original | {"record_id": "r2", "evidences": [a]}]
    prediction["records"] = [original | {"evidences": [a]}, original | {"record_id": "r2", "evidences": [b]}]
    assert score(raw)["evidence_location_rate"] == 1
    prediction["records"].reverse()
    assert score(raw)["evidence_location_rate"] == 1


@pytest.mark.parametrize("mutation", ["duplicate_paper", "duplicate_pdf", "wrong_source", "unknown_paper", "partial_failure", "nan"])
def test_invalid_inputs_are_rejected(mutation):
    raw = inputs(2)
    if mutation == "duplicate_paper":
        raw[0]["papers"][1]["paper_id"] = "0"
    elif mutation == "duplicate_pdf":
        raw[0]["papers"][1] = raw[0]["papers"][0] | {"paper_id": "1"}
    elif mutation == "wrong_source":
        raw[2]["papers"][0]["source_sha256s"] = ["f"*64]
    elif mutation == "unknown_paper":
        raw[2]["papers"][0]["paper_id"] = "outside"
    elif mutation == "partial_failure":
        raw[2]["papers"][0]["status"] = "failed"
    elif mutation == "nan":
        raw[2]["papers"][0]["records"][0]["fields"]["tc_k"] = float("nan")
    with pytest.raises(ValueError):
        score(raw)


@pytest.mark.parametrize("bbox", [[0, 0, 0, 1], [0, 0, 2, 1], [0, 0, float("nan"), 1]])
def test_invalid_region_rejected(bbox):
    with pytest.raises(ValidationError):
        Region(file_sha256="a"*64, pdf_page=1, bbox=bbox, quote="Tc")


def test_reviewed_category_regression_blocks_gate_even_when_total_improves():
    raw = inputs(3, "human")
    for paper, category in zip(raw[0]["papers"], ("scanned", "multipage_table", "multi_pressure")):
        paper["categories"] = ["digital", "english", category]
    raw[1]["papers"][0] = copy.deepcopy(raw[2]["papers"][0])
    raw[2]["papers"][0].update(status="failed", records=[])
    report = score(raw)
    assert report["new_complex_recall"] > report["legacy_complex_recall"]
    assert not quality_gate_passed(report)


@pytest.mark.parametrize("mutation", ["summary", "missing_category", "duplicate_id", "duplicate_pdf", "checks", "count", "nan", "missing", "unsupported"])
def test_gate_rejects_forged_or_incomplete_summary(mutation):
    report = score(inputs(3, "human"))
    if mutation == "summary":
        report["new_f1"] = .99
    elif mutation == "missing_category":
        report["category_papers"].pop("english")
    elif mutation == "duplicate_id":
        report["runs"]["new"]["papers"][1]["paper_id"] = "0"
    elif mutation == "duplicate_pdf":
        rows = report["runs"]["new"]["papers"]
        rows[1]["main_sha256"] = rows[0]["main_sha256"]
        rows[1]["source_sha256s"] = rows[0]["source_sha256s"]
    elif mutation == "checks":
        report["checks"]["failure_recovery"]["passed"] = False
    elif mutation == "count":
        report["annotated_papers"] = 4
    elif mutation == "nan":
        report["runs"]["new"]["total"]["f1"] = float("nan")
    elif mutation == "missing":
        report["runs"]["new"]["missing_papers"] = ["1"]
    elif mutation == "unsupported":
        report["unsupported_writes"] = 1
    assert not quality_gate_passed(report)


def test_cli_reads_artifacts_and_refuses_to_overwrite_inputs(tmp_path):
    args = []
    for name, value in zip(("corpus", "legacy", "new", "checks"), inputs()):
        path = tmp_path / f"{name}.json"
        path.write_text(json.dumps(value))
        args.extend([f"--{name}", str(path)])
    output = tmp_path / "report.json"
    command = [sys.executable, "-m", "backend.ingest.pdf_benchmark", *args, "--output", str(output)]
    result = subprocess.run(command, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    report = json.loads(output.read_text())
    assert report["new_f1"] == 1 and not report["quality_gate_passed"]
    command[-1] = str(tmp_path / "corpus.json")
    result = subprocess.run(command, capture_output=True, text=True, timeout=30)
    assert result.returncode != 0
    assert json.loads((tmp_path / "corpus.json").read_text())["kind"] == "synthetic"

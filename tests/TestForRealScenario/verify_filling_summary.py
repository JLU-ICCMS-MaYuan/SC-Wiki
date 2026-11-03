"""真实失败响应重放与概述归并边界；测试构造声明不代表模型科学验收。"""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from backend.ingest.scientific_form_filling import apply_plan

FIXTURE = Path(__file__).with_name("fixtures") / "h3s-filling-failed.json"


def replay_inputs():
    data = json.loads(FIXTURE.read_text())
    states = deepcopy(data["states"])
    for state in states:
        state["property_modules"] = []
    for item in data["candidates"]:
        si, mi, ri = [int(part[1:]) for part in item["candidate_id"].split(":")]
        while len(states[si]["property_modules"]) <= mi:
            states[si]["property_modules"].append({"module_code": "superconductive_properties", "records": []})
        records = states[si]["property_modules"][mi]["records"]
        assert len(records) == ri
        records.append(deepcopy(item["record"]))
    return data, states


def declared_response(data):
    response = deepcopy(data["response"])
    response["candidate_relations"] = [{
        "summary_candidate_id": "s1:m0:r1", "canonical_candidate_id": "s1:m0:r0",
        "relation": "summary_of_range", "source_ids": ["source-15", "source-41"],
        "reason": "测试构造：原文概述200 K与同一200 GPa结果的191–204 K范围对应，保留原始表达及双方来源。",
    }]
    return response


def test_original_failed_response_still_requires_explicit_relation():
    data, states = replay_inputs()
    with pytest.raises(ValueError, match="整理丢失"):
        apply_plan(states, data["sources"], data["response"])


@pytest.mark.parametrize("summary_method", ["unknown", "allen_dynes"])
def test_source_bound_summary_merge_preserves_original_and_detailed_endpoints(summary_method):
    data, states = replay_inputs()
    summary = states[1]["property_modules"][0]["records"][1]
    summary["method_code"] = summary_method
    if summary_method == "allen_dynes":
        summary["method_raw"] = "Allen-Dynes-modified McMillan equation"
    before = deepcopy(states)
    result, audit = apply_plan(states, data["sources"], declared_response(data))
    assert states == before
    assert sum(len(m["records"]) for s in result for m in s["property_modules"]) == 4
    detailed = result[1]["property_modules"][0]["records"][0]
    assert (detailed["value_min"], detailed["value_max"]) == (191, 204)
    relation = audit["summary_relations"]["s1:m0:r1"]
    assert relation["original_record"]["value_number"] == 200
    assert relation["canonical_candidate_id"] == "s1:m0:r0"
    assert audit["candidate_dispositions"]["s1:m0:r1"]["records"] == audit["candidate_dispositions"]["s1:m0:r0"]["records"]


@pytest.mark.parametrize("mutation", ["unknown_candidate", "different_state", "known_method", "known_mu", "known_condition", "outside_range", "unread_source", "one_sided_source", "lost_endpoint"])
def test_declared_relation_cannot_hide_distinct_or_unpreserved_science(mutation):
    data, states = replay_inputs()
    response = declared_response(data)
    relation = response["candidate_relations"][0]
    summary = states[1]["property_modules"][0]["records"][1]
    if mutation == "unknown_candidate":
        relation["summary_candidate_id"] = "s1:m0:r9"
    elif mutation == "different_state":
        relation["canonical_candidate_id"] = "s0:m0:r0"
    elif mutation == "known_method":
        summary["method_code"] = "scdft"
    elif mutation == "known_mu":
        summary["payload"]["parameters"]["mu_star"] = 0.11
    elif mutation == "known_condition":
        summary["payload"]["calculation_conditions"]["calculation_code"] = "EPW"
    elif mutation == "outside_range":
        summary["value_number"] = 250
    elif mutation == "unread_source":
        relation["source_ids"] = ["not-read"]
    elif mutation == "one_sided_source":
        relation["source_ids"] = ["source-41"]
    elif mutation == "lost_endpoint":
        detailed = response["records"][1]["values"]
        detailed["value_min"] = 192
    with pytest.raises(ValueError):
        apply_plan(states, data["sources"], response)


def test_detailed_range_can_still_map_to_two_explicit_points():
    data, states = replay_inputs()
    response = declared_response(data)
    template = response["records"][1]
    points = []
    for tc, mu in [(191, 0.13), (204, 0.1)]:
        point = deepcopy(template)
        point["values"].update(value_kind="number", value_number=tc, value_min=None,
                               value_max=None, value_raw=f"{tc} K")
        point["values"]["parameters"]["mu_star"] = mu
        points.append(point)
    response["records"][1:2] = points
    result, audit = apply_plan(states, data["sources"], response)
    records = result[1]["property_modules"][0]["records"]
    assert [(r["value_number"], r["payload"]["parameters"]["mu_star"]) for r in records] == [(191, 0.13), (204, 0.1)]
    assert len({r["payload"]["tc_group"]["group_key"] for r in records}) == 1
    assert len({r["payload"]["tc_group"]["method_key"] for r in records}) == 1
    assert audit["summary_relations"]["s1:m0:r1"]["original_record"]["value_number"] == 200

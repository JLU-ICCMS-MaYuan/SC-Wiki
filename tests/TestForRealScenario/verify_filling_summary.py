"""真实失败响应重放：复用通用候选去向，不增加概述特例。"""
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


def test_original_response_uses_general_candidate_mapping():
    data, states = replay_inputs()
    result, audit = apply_plan(states, data["sources"], data["response"])
    detailed = result[1]["property_modules"][0]["records"][0]
    assert (detailed["value_min"], detailed["value_max"]) == (191, 204)
    summary = audit["candidate_dispositions"]["s1:m0:r1"]
    assert summary["original_record"]["value_number"] == 200
    assert summary["records"] == audit["candidate_dispositions"]["s1:m0:r0"]["records"]
    assert "summary_relations" not in audit


@pytest.mark.parametrize("mutation", ["unknown_candidate", "different_state", "unread_source", "lost_candidate"])
def test_invalid_identity_or_missing_candidate_remains_blocked(mutation):
    data, states = replay_inputs()
    answer = deepcopy(data["response"])
    target = answer["records"][1]
    if mutation == "unknown_candidate":
        target["candidate_ids"].append("s1:m0:r9")
    elif mutation == "different_state":
        target["candidate_ids"].append("s0:m0:r0")
    elif mutation == "unread_source":
        target["source_ids"] = ["not-read"]
    else:
        target["candidate_ids"].remove("s1:m0:r1")
    with pytest.raises(ValueError):
        apply_plan(states, data["sources"], answer)

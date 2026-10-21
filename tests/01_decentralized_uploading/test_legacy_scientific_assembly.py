"""汇总模型不再拥有科学数值最终写入权。"""

from backend.ingest.legacy_scientific_assembly import assemble_legacy_candidates


def _state(pressure, tc, symbol="P6/mmm"):
    return {"material": "LaSc2H24", "scope": "current_paper", "pressure_value_gpa": pressure,
            "reported_space_group_symbol": symbol, "state_kind": "theoretical",
            "tc_results": [{"tc_value_k": tc, "value_raw": f"{tc} K", "unit_raw": "K",
                            "evidence": {"quote": f"{tc} K at {pressure} GPa"}}],
            "evidence": {"quote": f"LaSc2H24 at {pressure} GPa"}}


def test_same_pressure_fragments_merge_without_losing_distinct_tc():
    candidates = [{"material_states": [_state(167, 316), _state(250, 331)], "_source": {"file_id": "main"}},
                  {"material_states": [_state(167, 316, None)], "_source": {"file_id": "main"}}]
    states, issues = assemble_legacy_candidates(candidates)
    assert len(states) == 2
    assert all(issue["code"] == "candidate_missing" for issue in issues)
    assert sorted(state["pressure_value_gpa"] for state in states) == [167, 250]
    assert all(sum(len(m["records"]) for m in state["property_modules"]) == 1 for state in states)


def test_old_chunk_aliases_preserve_numbers_and_merge_equivalent_tc():
    exact = _state(167, 316)
    exact["tc_results"] = [{"value": 316, "unit": "K", "value_raw": "316 K at 167 GPa",
                            "evidence": {"quote": "316 K at 167 GPa"}}]
    duplicate = _state(167, 316)
    duplicate["tc_results"] = [{"value_min": 316, "value_max": 316, "unit": "K",
                                "value_raw": "up to 316 K", "evidence": {"quote": "up to 316 K"}}]
    ranged = _state(167, 316)
    ranged["tc_results"] = [{"value_min": 285, "value_max": 316, "unit": "K",
                             "value_raw": "285 to 316 K", "method": "isotropic Eliashberg equations",
                             "evidence": {"quote": "285 to 316 K"}}]
    states, _ = assemble_legacy_candidates([
        {"material_states": [exact, duplicate, ranged], "_source": {"file_id": "main"}},
    ])
    records = states[0]["property_modules"][0]["records"]
    assert len(records) == 2
    assert {(item["value_number"], item["value_min"], item["value_max"], item["method_code"])
            for item in records} == {(316, None, None, "unknown"),
                                     (None, 285, 316, "isotropic_eliashberg")}

"""科学验收不能靠JSON或自报大误差通过，也不能把柱子交换材料。"""
from copy import deepcopy
from pathlib import Path
import importlib.util,json

ROOT=Path(__file__).parents[2]
spec=importlib.util.spec_from_file_location("fig4_reference",ROOT/"tests/TestForRealScenario/fig4_pixel_reference.py")
gate=importlib.util.module_from_spec(spec);spec.loader.exec_module(gate)
FIX=Path(__file__).parent/"fixtures/flash_fig4_scientific"
REF=json.loads((FIX/"pixel-reference.json").read_text())


def valid_facts():
    out=[]
    for t in REF["items"]:
        quantity=t["quantity"]
        out.append({"point":{"material":t["material"],"mu_star":t["mu_star"],"pressure_value_gpa":t["pressure"],
                            "x":sum(t["x_span"])/2*1000/REF["image_size"][0]},
          "quantity":quantity,"unit":"K" if quantity=="tc" else "dimensionless" if quantity=="lambda_ep" else "states/(eV Å³)",
          "crop_bbox":REF["native_image_bbox_page"],"value_number":t["value"],"calculated_value":t["value"]})
    return out


def test_reference_values_and_original_bar_identities_pass():
    assert not gate.validate(valid_facts(),REF)


def test_real_old_flash_results_remain_failed():
    issues=gate.validate(json.loads((FIX/"old-flash-facts.json").read_text()),REF)
    assert any(x["code"]=="missing" for x in issues)
    assert any(x["code"]=="value_mismatch" for x in issues)


def test_swapping_bars_cannot_pass_with_numerically_correct_values():
    facts=valid_facts();facts[0]["point"]["x"],facts[1]["point"]["x"]=facts[1]["point"]["x"],facts[0]["point"]["x"]
    assert any(i["code"]=="wrong_bar_identity" for i in gate.validate(facts,REF))


def test_self_reported_precision_cannot_hide_wrong_value_or_wrong_unit():
    facts=valid_facts();facts[0]["calculated_value"]=1;facts[0]["reading_precision"]=99999
    assert any(i["code"]=="value_mismatch" for i in gate.validate(facts,REF))
    facts=valid_facts();facts[0]["unit"]="states/eV/cell"
    assert any(i["code"]=="unit_mismatch" for i in gate.validate(facts,REF))


def test_fake_prh9_zero_and_missing_mu_pair_are_rejected():
    facts=valid_facts();extra=deepcopy(next(f for f in facts if f["quantity"]=="tc"))
    extra["point"]["material"]="PrH9";extra["value_number"]=0;extra["calculated_value"]=0;facts.append(extra)
    assert any(i["code"]=="unexpected_or_unreadable_point" for i in gate.validate(facts,REF))
    facts=valid_facts();facts.pop()
    assert any(i["code"]=="missing" for i in gate.validate(facts,REF))

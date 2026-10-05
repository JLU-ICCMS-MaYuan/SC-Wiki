from decimal import Decimal, getcontext, localcontext

from backend.db_helpers import (
    build_system_key,
    normalize_formula,
    parse_formula_composition,
)


def test_build_system_key_sorts_symbols():
    assert build_system_key(["La", "H"]) == ("H-La", ["H", "La"])


def test_parse_formula_composition_counts_atoms():
    assert parse_formula_composition("LaH10") == {"La": Decimal("1"), "H": Decimal("10")}


def test_parse_formula_composition_supports_decimal_amounts():
    assert parse_formula_composition("Ba0.6K0.4Fe2As2") == {
        "Ba": Decimal("0.6"),
        "K": Decimal("0.4"),
        "Fe": Decimal("2"),
        "As": Decimal("2"),
    }


def test_parse_formula_composition_rejects_trailing_garbage():
    try:
        parse_formula_composition("LaH10xxx")
    except ValueError:
        return
    raise AssertionError("expected trailing garbage to raise ValueError")


def test_parse_formula_composition_expands_groups_and_subscripts():
    # #120：分组写法不能被截成其中一段而改变材料身份。
    assert parse_formula_composition("La(OH)2") == {"La": Decimal("1"), "O": Decimal("2"), "H": Decimal("2")}
    assert parse_formula_composition("(H2S)2H2") == {"H": Decimal("6"), "S": Decimal("2")}
    assert parse_formula_composition("(H₂S)₂H₂") == {"H": Decimal("6"), "S": Decimal("2")}
    assert normalize_formula("(H2S)2H2")[1] == ["H", "S"]


def test_parse_formula_composition_rejects_unbalanced_or_alternative_groups():
    for formula in ("(H2S", "H2S)", "(La,Ce)H9", "()H2"):
        try:
            parse_formula_composition(formula)
        except ValueError:
            continue
        raise AssertionError(f"expected {formula} to raise ValueError")


def test_parse_formula_composition_rejects_zero_amounts():
    try:
        parse_formula_composition("La0H10")
    except ValueError:
        return
    raise AssertionError("expected zero amount to raise ValueError")


def test_parse_formula_composition_rejects_unknown_element_symbols():
    for formula in ("Xx2", "Aa1"):
        try:
            parse_formula_composition(formula)
        except ValueError:
            continue
        raise AssertionError(f"expected unknown element in {formula} to raise ValueError")


def test_normalize_formula_sorts_symbols():
    normalized, elements, composition, ratios = normalize_formula("LaH10")
    assert normalized == "H10La"
    assert elements == ["H", "La"]
    assert composition == {"La": Decimal("1"), "H": Decimal("10")}
    with localcontext() as ctx:
        ctx.prec = 50
        assert ratios["La"] == Decimal("1") / Decimal("11")
        assert ratios["H"] == Decimal("10") / Decimal("11")


def test_normalize_formula_formats_decimal_amounts():
    normalized, elements, composition, ratios = normalize_formula("Ba0.6K0.4Fe2As2")
    assert normalized == "As2Ba0.6Fe2K0.4"
    assert elements == ["As", "Ba", "Fe", "K"]
    assert composition == {"Ba": Decimal("0.6"), "K": Decimal("0.4"), "Fe": Decimal("2"), "As": Decimal("2")}
    assert ratios["Ba"] == Decimal("0.6") / Decimal("5")
    assert ratios["K"] == Decimal("0.4") / Decimal("5")
    assert ratios["Fe"] == Decimal("2") / Decimal("5")
    assert ratios["As"] == Decimal("2") / Decimal("5")


def test_normalize_formula_does_not_emit_scientific_notation():
    normalized, _, _, _ = normalize_formula("H0.00001")
    assert normalized == "H0.00001"
    assert parse_formula_composition(normalized) == {"H": Decimal("0.00001")}


def test_normalize_formula_keeps_very_small_decimal_amounts():
    normalized, _, _, _ = normalize_formula("H0.0000000000001")
    assert normalized == "H0.0000000000001"
    assert "e" not in normalized.lower()
    assert parse_formula_composition(normalized) == {"H": Decimal("0.0000000000001")}


def test_normalize_formula_keeps_sub_float_decimal_amounts():
    amount = "0." + ("0" * 400) + "1"
    normalized, _, _, _ = normalize_formula(f"H{amount}")
    assert normalized == f"H{amount}"
    assert "e" not in normalized.lower()
    assert parse_formula_composition(normalized) == {"H": Decimal(amount)}


def test_normalize_formula_keeps_many_significant_decimal_digits():
    amount = "0.123456789012345678901234567890"
    normalized, _, _, _ = normalize_formula(f"H{amount}")
    assert normalized == f"H{amount.rstrip('0')}"
    assert parse_formula_composition(normalized) == {"H": Decimal(amount)}


def test_normalize_formula_does_not_round_near_integer_decimal_to_integer():
    amount = "1.000000000000000000000000000001"
    normalized, _, _, _ = normalize_formula(f"H{amount}")
    assert normalized == f"H{amount}"
    assert parse_formula_composition(normalized) == {"H": Decimal(amount)}


def test_normalize_formula_ratios_ignore_global_decimal_precision():
    with localcontext() as ctx:
        ctx.prec = 2
        _, _, _, ratios = normalize_formula("H1La10")

    assert getcontext().prec != 50
    with localcontext() as ctx:
        ctx.prec = 50
        assert ratios["H"] == Decimal("1") / Decimal("11")
        assert ratios["La"] == Decimal("10") / Decimal("11")

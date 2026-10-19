import numpy as np
import pytest
from pymatgen.symmetry.groups import SpaceGroup

from backend.services.wyckoff_rounding import restore_rounded_site


@pytest.mark.parametrize(("symbol", "tokens", "multiplicity"), [
    ("P6/mmm", ["0.333", "0.667", "0.000"], 2),
    ("P6/mmm", ["0.759", "0.519", "0.500"], 6),
    ("R3m", ["0.66667", "0.33333", "0.62631"], 3),
])
def test_rounding_recovery_obeys_reported_precision_and_strict_symmetry(symbol, tokens, multiplicity):
    group = SpaceGroup(symbol)
    derived, record = restore_rounded_site(group, tokens, multiplicity)
    assert record["reported_tokens"] == tokens
    assert len(group.get_orbit(derived, tol=1e-7)) == multiplicity
    assert np.all(np.abs(record["coordinate_changes"]) <= np.array(record["rounding_half_width"]) + 1e-12)
    assert record["derived_coordinates"] == derived
    # 完成后的对称坐标再次处理不继续漂移。
    same, adjustment = restore_rounded_site(group, [f"{v:.12f}" for v in derived], multiplicity)
    assert same == pytest.approx(derived, abs=1e-12)
    assert adjustment is None


@pytest.mark.parametrize("tokens,multiplicity", [
    (["0.759", "0.525", "0.500"], 6),
    (["0.33", "0.67", "0.00"], 1),
    (["0.1", "0.1", "0.1"], 5),
    (["0.759", "0.519", "0.500"], 0),
])
def test_conflicting_coordinates_and_wrong_multiplicity_are_not_repaired(tokens, multiplicity):
    with pytest.raises(ValueError):
        restore_rounded_site(SpaceGroup("P6/mmm"), tokens, multiplicity)


def test_exact_site_keeps_reported_coordinates_without_reconstruction():
    result, adjustment = restore_rounded_site(SpaceGroup("P6/mmm"), ["0.762", "0", "0"], 6)
    assert result == [0.762, 0, 0]
    assert adjustment is None

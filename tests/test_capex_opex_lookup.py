"""
Unit tests for src/relife_financial/data/lookup.py

Covers: known prices, material averaging, Czechia alias, OPEX zero for
insulation, mixed renovation packages, and error paths.
"""
import pytest

from relife_financial.data.lookup import (
    ALL_ACTIONS,
    compute_capex,
    compute_opex,
    supported_actions,
    supported_countries,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _Action:
    """Minimal stub that satisfies the ActionLike protocol."""

    def __init__(self, action, *, area_m2=None, capacity_kw=None, material=None):
        self.action = action
        self.area_m2 = area_m2
        self.capacity_kw = capacity_kw
        self.material = material


# ---------------------------------------------------------------------------
# supported_countries / supported_actions
# ---------------------------------------------------------------------------

def test_supported_countries_count():
    assert len(supported_countries()) == 27


def test_supported_countries_includes_expected():
    countries = supported_countries()
    for name in ("Austria", "Italy", "Germany", "Spain", "Czech Republic"):
        assert name in countries


def test_supported_actions_count():
    assert len(supported_actions()) == 10


def test_supported_actions_matches_all_actions():
    assert set(supported_actions()) == set(ALL_ACTIONS)


# ---------------------------------------------------------------------------
# CAPEX — area-based actions
# ---------------------------------------------------------------------------

def test_capex_wall_insulation_austria():
    """Known price: Austria wall insulation = 154.31 €/m²."""
    result = compute_capex("Austria", [_Action("Wall insulation", area_m2=1.0)])
    assert pytest.approx(result, rel=1e-3) == 154.31


def test_capex_wall_insulation_scales_with_area():
    result_10 = compute_capex("Austria", [_Action("Wall insulation", area_m2=10.0)])
    result_20 = compute_capex("Austria", [_Action("Wall insulation", area_m2=20.0)])
    assert pytest.approx(result_20, rel=1e-9) == result_10 * 2


def test_capex_roof_insulation_accessible_austria():
    result = compute_capex("Austria", [_Action("Roof insulation - Accessible", area_m2=1.0)])
    assert result > 0


def test_capex_floor_insulation_austria():
    result = compute_capex("Austria", [_Action("Floor insulation", area_m2=1.0)])
    assert result > 0


def test_capex_windows_austria():
    result = compute_capex("Austria", [_Action("Windows", area_m2=1.0)])
    assert result > 0


# ---------------------------------------------------------------------------
# CAPEX — capacity-based actions
# ---------------------------------------------------------------------------

def test_capex_heat_pump_austria_7kw():
    """Doc example: Austria heat pump 7 kW ≈ €24 386."""
    result = compute_capex("Austria", [_Action("Air-water Heat Pump", capacity_kw=7.0)])
    assert pytest.approx(result, rel=1e-3) == 24386.74


def test_capex_heat_pump_scales_with_capacity():
    result_5 = compute_capex("Austria", [_Action("Air-water Heat Pump", capacity_kw=5.0)])
    result_10 = compute_capex("Austria", [_Action("Air-water Heat Pump", capacity_kw=10.0)])
    # Non-linear due to fixed cost, but larger capacity must cost more
    assert result_10 > result_5


def test_capex_pv_austria():
    """Austria PV has only a €/kW price (no fixed cost)."""
    result_5 = compute_capex("Austria", [_Action("PV", capacity_kw=5.0)])
    result_10 = compute_capex("Austria", [_Action("PV", capacity_kw=10.0)])
    assert pytest.approx(result_10, rel=1e-9) == result_5 * 2


def test_capex_condensing_boiler_austria():
    result = compute_capex("Austria", [_Action("Condensing boiler", capacity_kw=14.0)])
    assert result > 0


def test_capex_solar_thermal_austria():
    result = compute_capex("Austria", [_Action("Solar thermal panels", capacity_kw=4.2)])
    assert result > 0


# ---------------------------------------------------------------------------
# CAPEX — multi-action package
# ---------------------------------------------------------------------------

def test_capex_multi_action_is_sum_of_parts():
    wall = compute_capex("Italy", [_Action("Wall insulation", area_m2=50.0)])
    hp = compute_capex("Italy", [_Action("Air-water Heat Pump", capacity_kw=8.0)])
    combined = compute_capex(
        "Italy",
        [
            _Action("Wall insulation", area_m2=50.0),
            _Action("Air-water Heat Pump", capacity_kw=8.0),
        ],
    )
    assert pytest.approx(combined, rel=1e-9) == wall + hp


# ---------------------------------------------------------------------------
# CAPEX — material filtering
# ---------------------------------------------------------------------------

def test_capex_material_filter_returns_single_variant():
    """When a specific material is provided it should not equal the average of all materials."""
    eps = compute_capex("Croatia", [_Action("Wall insulation", area_m2=1.0, material="EPS")])
    gw = compute_capex("Croatia", [_Action("Wall insulation", area_m2=1.0, material="GW")])
    avg = compute_capex("Croatia", [_Action("Wall insulation", area_m2=1.0)])
    # All three should be positive
    assert eps > 0 and gw > 0 and avg > 0
    # Average should sit between the two extremes (or at least differ from at least one)
    assert not (eps == gw == avg)


def test_capex_unknown_material_falls_back_to_average():
    """An unrecognised material string should fall back to the average of all variants."""
    avg = compute_capex("Croatia", [_Action("Wall insulation", area_m2=1.0)])
    fallback = compute_capex("Croatia", [_Action("Wall insulation", area_m2=1.0, material="XYZ")])
    assert pytest.approx(fallback, rel=1e-9) == avg


# ---------------------------------------------------------------------------
# CAPEX — country name normalisation
# ---------------------------------------------------------------------------

def test_capex_czechia_alias():
    c1 = compute_capex("Czechia", [_Action("Wall insulation", area_m2=50.0)])
    c2 = compute_capex("Czech Republic", [_Action("Wall insulation", area_m2=50.0)])
    assert pytest.approx(c1, rel=1e-9) == c2


def test_capex_country_name_case_insensitive():
    lower = compute_capex("austria", [_Action("Wall insulation", area_m2=10.0)])
    upper = compute_capex("AUSTRIA", [_Action("Wall insulation", area_m2=10.0)])
    assert pytest.approx(lower, rel=1e-9) == upper


# ---------------------------------------------------------------------------
# OPEX
# ---------------------------------------------------------------------------

def test_opex_heat_pump_austria():
    result = compute_opex("Austria", [_Action("Air-water Heat Pump")])
    assert pytest.approx(result, rel=1e-3) == 331.63


def test_opex_insulation_is_zero():
    """Insulation and windows have no OPEX entry — must return 0."""
    actions = [
        _Action("Wall insulation", area_m2=80.0),
        _Action("Floor insulation", area_m2=40.0),
        _Action("Windows", area_m2=20.0),
    ]
    assert compute_opex("Austria", actions) == 0.0


def test_opex_mixed_package_sums_correctly():
    hp = compute_opex("Austria", [_Action("Air-water Heat Pump")])
    pv = compute_opex("Austria", [_Action("PV")])
    combined = compute_opex("Austria", [_Action("Air-water Heat Pump"), _Action("PV")])
    assert pytest.approx(combined, rel=1e-9) == hp + pv


def test_opex_all_actions_no_opex_for_insulation_and_windows():
    """Package with only area-based actions should yield exactly 0 OPEX."""
    actions = [
        _Action("Wall insulation", area_m2=1.0),
        _Action("Wall insulation - additional", area_m2=1.0),
        _Action("Roof insulation - Accessible", area_m2=1.0),
        _Action("Roof insulation - Makeover", area_m2=1.0),
        _Action("Floor insulation", area_m2=1.0),
        _Action("Windows", area_m2=1.0),
    ]
    assert compute_opex("Germany", actions) == 0.0


def test_opex_czechia_alias():
    c1 = compute_opex("Czechia", [_Action("PV")])
    c2 = compute_opex("Czech Republic", [_Action("PV")])
    assert pytest.approx(c1, rel=1e-9) == c2


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------

def test_capex_unknown_country_raises():
    with pytest.raises(ValueError, match="not supported"):
        compute_capex("Narnia", [_Action("PV", capacity_kw=5.0)])


def test_opex_unknown_country_raises():
    with pytest.raises(ValueError, match="not supported"):
        compute_opex("Westeros", [_Action("Air-water Heat Pump")])


def test_capex_unknown_action_raises():
    with pytest.raises(ValueError, match="Unknown renovation action"):
        compute_capex("Italy", [_Action("Magic insulation", area_m2=10.0)])


def test_capex_missing_area_m2_raises():
    with pytest.raises(ValueError, match="area_m2 is required"):
        compute_capex("Italy", [_Action("Wall insulation")])


def test_capex_missing_capacity_kw_raises():
    with pytest.raises(ValueError, match="capacity_kw is required"):
        compute_capex("Italy", [_Action("Air-water Heat Pump")])


def test_capex_empty_actions_returns_zero():
    assert compute_capex("Austria", []) == 0.0


def test_opex_empty_actions_returns_zero():
    assert compute_opex("Austria", []) == 0.0

"""Tests for the Monte Carlo KPI engine in simulation_engine.py."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src" / "relife_financial" / "Indicator Modules"))

from simulation_engine import PBP, create_scheme_definitions, get_kpi_results, prepare_cashflow_inputs


def _p50(capex, scheme):
    results = get_kpi_results(
        capex=capex,
        annual_energy_savings=27400,
        annual_maintenace_cost=2000,
        project_lifetime=20,
        schemes=[scheme],
        n_sims=200,
    )
    return {kpi: values["P50"] for kpi, values in results[scheme[0]]["summary"]["percentiles"].items()}


def test_full_loan_rounded_to_whole_euros_has_no_roi_or_irr():
    """#13: a 100% loan rounded to whole euros, with savings above every loan payment."""
    p50 = _p50(8500.40, ("bank_loan", {"loan_amount": 8500, "term_years": 10}))
    assert p50["PBP"] == 0
    assert p50["ROI"] is None
    assert p50["IRR"] is None


def test_payback_is_when_cumulative_cash_flow_stays_positive():
    """#13: nothing paid upfront, two years out of pocket, then recovery."""
    assert PBP([0, -30, -30, 40, 40]) == pytest.approx(3.5)


def test_loan_payback_is_not_floored_at_term():
    """#15: an 80% loan pays back in about 8.5 years, inside its 20-year term."""
    assert _p50(60000, ("bank_loan", {"loan_amount": 48000, "term_years": 20}))["PBP"] < 20


@pytest.mark.parametrize(
    "scheme_type, details, principal",
    [
        ("bank_loan", {"loan_amount": 30000, "term_years": 30}, 30000),
        ("green_bond_loan", {"gb_proceeds": 30000, "term_years": 30, "fixed_interest": 0, "OM_green": 0}, 30000),
        ("green_bond_bullet", {"gb_proceeds": 30000, "term_years": 30, "fixed_interest": 0, "OM_green": 0}, 30000),
        ("on_bill", {"term_years": 30, "fixed_interest": 0}, 60000),
        ("epc_guaranteed_savings", {"term_years": 30, "gs": 0}, 60000),
        ("lending_crowdfunding", {"loan_crowd": 30000, "fixed_interest": 0, "term_years": 30, "fee_plat": 0}, 30000),
    ],
)
def test_loan_longer_than_simulation_is_fully_repaid(scheme_type, details, principal):
    """#14: a 30-year loan in a 20-year simulation, with zero rates, prices and O&M."""
    lifetime = 20
    (scheme,) = create_scheme_definitions(
        capex=60000,
        annual_energy_savings=1,
        annual_maintenace_cost=0,
        project_lifetime=lifetime,
        schemes=[(scheme_type, details)],
    )
    zeros = [0.0] * lifetime
    inputs = prepare_cashflow_inputs(scheme["base_inputs"], zeros, zeros, loan_interest_rate=zeros)
    _, _, outflows = scheme["cashflow_function"](**inputs)
    assert sum(outflows[1:]) == pytest.approx(principal)

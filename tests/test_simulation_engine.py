"""Tests for the Monte Carlo KPI engine in simulation_engine.py."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src" / "relife_financial" / "Indicator Modules"))

from simulation_engine import PBP, get_kpi_results


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

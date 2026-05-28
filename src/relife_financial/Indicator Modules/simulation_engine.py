"""
Monte Carlo simulation engine for financial risk assessment.

Supports 12 financing scheme families across 4 categories:
  - self_financed:  equity
  - debt_financed:  bank_loan, green_bond_loan, green_bond_bullet
  - esco_zero_capex: on_bill, operational_lease, epc_shared_savings,
                     epc_first_out, epc_guaranteed_savings
  - crowdfunding:   lending_crowdfunding, royalty_crowdfunding, equity_crowdfunding

Scenario calibration:
  - Inflation / interest rates: ECB-aligned forward-looking (2-5% range)
  - Electricity prices: European residential market data
  - Energy savings: stochastic Normal multiplicative factor (P10 = 0.70x)
  - Discount rates: homeowner opportunity cost (3-7%)
"""

from __future__ import annotations

import math
from typing import Any, Callable

import numpy as np
import numpy_financial as npf


# ─────────────────────────────────────────────────────────────────────────────
# Custom exceptions
# ─────────────────────────────────────────────────────────────────────────────

class FinancialSimulationError(Exception):
    """Base exception for financial simulation failures."""


class ExperimentConfigurationError(FinancialSimulationError):
    """Raised when the experiment configuration is incomplete or invalid."""


class FinancialInputError(FinancialSimulationError):
    """Raised when required numerical inputs are missing or invalid."""


class SchemeConfigurationError(FinancialSimulationError):
    """Raised when a financing scheme is missing required details."""


class SimulationComputationError(FinancialSimulationError):
    """Raised when KPI or cash-flow computation fails."""


# ─────────────────────────────────────────────────────────────────────────────
# Validation helpers
# ─────────────────────────────────────────────────────────────────────────────

def _ensure(condition: bool, message: str, exc_type: type = FinancialInputError) -> None:
    if not condition:
        raise exc_type(message)


def _is_finite_number(value: Any) -> bool:
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def _validate_finite_number(name: str, value: Any, allow_none: bool = False) -> None:
    if value is None and allow_none:
        return
    _ensure(_is_finite_number(value), f"{name} must be a finite number. Got: {value!r}")


def _validate_flows(flows: Any, *, require_initial_outflow: bool = False) -> None:
    _ensure(
        isinstance(flows, list),
        f"Cash-flow function must return a list. Got: {type(flows).__name__}",
        SimulationComputationError,
    )
    _ensure(len(flows) >= 2, f"Cash-flow list must have >=2 values. Got: {len(flows)}", SimulationComputationError)
    for idx, value in enumerate(flows):
        _ensure(_is_finite_number(value), f"Cash-flow at index {idx} must be finite. Got: {value!r}", SimulationComputationError)


# ─────────────────────────────────────────────────────────────────────────────
# KPI histogram builder
# ─────────────────────────────────────────────────────────────────────────────

def _build_kpi_histogram_payload(
    name: str,
    values: Any,
    *,
    bins: int = 30,
    project_lifetime: int | None = None,
) -> dict:
    """Build histogram payload with feasible/infeasible split for frontend rendering."""
    raw = np.asarray(values, dtype=float)
    empty: dict = {
        "bin_edges": [],
        "feasible_counts": [],
        "infeasible_counts": [],
        "p10": None,
        "p50": None,
        "p90": None,
        "project_lifetime": int(project_lifetime) if project_lifetime is not None else None,
    }

    a = raw[np.isfinite(raw)]
    if a.size == 0:
        return empty

    if name in ("PBP", "DPP"):
        if project_lifetime is not None:
            infeasible_mask = a > float(project_lifetime)
        else:
            infeasible_mask = np.zeros_like(a, dtype=bool)
        if a.size == 1 or np.isclose(a.min(), a.max()):
            center = float(a[0])
            bin_edges = np.array([max(center - 0.5, 0.0), center + 0.5], dtype=float)
        else:
            bin_edges = np.histogram_bin_edges(a, bins=bins)
    else:
        if name in ("NPV", "IRR", "ROI"):
            infeasible_mask = a < 0
        else:
            infeasible_mask = np.zeros_like(a, dtype=bool)
        bin_edges = np.histogram_bin_edges(a, bins=bins)

    feasible = a[~infeasible_mask]
    infeasible = a[infeasible_mask]
    feasible_counts, _ = np.histogram(feasible, bins=bin_edges)
    infeasible_counts, _ = np.histogram(infeasible, bins=bin_edges)
    p10, p50, p90 = np.nanpercentile(a, [10, 50, 90])

    return {
        "bin_edges": bin_edges.tolist(),
        "feasible_counts": feasible_counts.tolist(),
        "infeasible_counts": infeasible_counts.tolist(),
        "p10": float(p10),
        "p50": float(p50),
        "p90": float(p90),
        "project_lifetime": int(project_lifetime) if project_lifetime is not None else None,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Market distribution helpers
# ─────────────────────────────────────────────────────────────────────────────

Z90 = 1.2815515655446004  # Phi^{-1}(0.90)


def pad_to_length(lst: list, length: int) -> list:
    """Extend list to `length` by repeating the last value."""
    return lst + [lst[-1]] * (length - len(lst)) if len(lst) < length else lst[:length]


def _mu_sigma_from_p10_p50_p90(p10, p50, p90):
    """Normal distribution parameters from P10/P50/P90 scenario paths."""
    p10 = np.asarray(p10, dtype=float)
    p50 = np.asarray(p50, dtype=float)
    p90 = np.asarray(p90, dtype=float)
    mu = p50
    sigma = np.maximum((p90 - p10) / (2.0 * Z90), 1e-12)
    return mu, sigma


def _log_mu_sigma_from_p10_p50_p90_prices(p10, p50, p90):
    """Lognormal parameters for electricity prices (keeps values positive)."""
    eps = 1e-9
    p10 = np.maximum(np.asarray(p10, dtype=float), eps)
    p50 = np.maximum(np.asarray(p50, dtype=float), eps)
    p90 = np.maximum(np.asarray(p90, dtype=float), eps)
    mu_ln = np.log(p50)
    sigma_ln = np.maximum((np.log(p90) - np.log(p10)) / (2.0 * Z90), 1e-12)
    return mu_ln, sigma_ln


def build_energy_savings_factor_distribution(downside_at_p10: float = 0.30) -> dict:
    """
    Model energy-savings uncertainty as a multiplicative Normal factor.
    P50 = 1.0x (base estimate), P10 = 1 - downside_at_p10.
    Default: P10 = 0.70x -- 30% downside at the 10th percentile.
    """
    _ensure(0.0 <= downside_at_p10 < 1.0, "downside_at_p10 must be in [0, 1).")
    p10 = 1.0 - downside_at_p10
    p50 = 1.0
    sigma = max((p50 - p10) / Z90, 1e-12)
    return {"mu": p50, "sigma": sigma, "p10": p10, "p50": p50, "p90": p50 + (p50 - p10)}


def build_market_distributions(
    inflation_rate_data: dict,
    electricity_prices_data: dict,
    interest_rate_data: dict,
    discount_rate_data: dict,
    project_lifetime: int,
) -> dict:
    """
    Derive per-year Normal/Lognormal distribution parameters from 3-scenario paths.

    Label conventions:
      inflation / interest:  optimistic = low (P10), pessimistic = high (P90)
      electricity prices:    pessimistic = low (P10), optimistic = high (P90)
                             (high prices = more savings revenue = favourable)
      discount rate:         optimistic = low (P10), pessimistic = high (P90)
    """
    T = min(project_lifetime, 30)

    infl_mu, infl_sigma = _mu_sigma_from_p10_p50_p90(
        pad_to_length(inflation_rate_data["optimistic"], T),
        pad_to_length(inflation_rate_data["moderate"], T),
        pad_to_length(inflation_rate_data["pessimistic"], T),
    )

    rate_mu, rate_sigma = _mu_sigma_from_p10_p50_p90(
        pad_to_length(interest_rate_data["optimistic"], T),
        pad_to_length(interest_rate_data["moderate"], T),
        pad_to_length(interest_rate_data["pessimistic"], T),
    )

    disc_mu, disc_sigma = _mu_sigma_from_p10_p50_p90(
        np.full(T, discount_rate_data["optimistic"][0], dtype=float),
        np.full(T, discount_rate_data["moderate"][0], dtype=float),
        np.full(T, discount_rate_data["pessimistic"][0], dtype=float),
    )

    # electricity: pessimistic=P10 (low), optimistic=P90 (high)
    elec_mu_ln, elec_sigma_ln = _log_mu_sigma_from_p10_p50_p90_prices(
        pad_to_length(electricity_prices_data["pessimistic"], T),
        pad_to_length(electricity_prices_data["moderate"], T),
        pad_to_length(electricity_prices_data["optimistic"], T),
    )

    return {
        "inflation":  {"mu": infl_mu,    "sigma": infl_sigma,               "dist": "normal",    "unit": "% y/y"},
        "loan_rate":  {"mu": rate_mu,    "sigma": rate_sigma,               "dist": "normal",    "unit": "% y/y"},
        "discount":   {"mu": disc_mu,    "sigma": disc_sigma,               "dist": "normal",    "unit": "fraction"},
        "elec_price": {"mu_ln": elec_mu_ln, "sigma_ln": elec_sigma_ln,      "dist": "lognormal", "unit": "EUR/kWh"},
        "T": T,
    }


# ─────────────────────────────────────────────────────────────────────────────
# KPI functions
# ─────────────────────────────────────────────────────────────────────────────

def IRR(flows: list) -> float:
    """Internal Rate of Return."""
    _validate_flows(flows)
    try:
        return npf.irr(flows)
    except Exception as exc:
        raise SimulationComputationError(f"Failed to compute IRR: {exc}") from exc


def NPV(d_r: float, flows: list) -> float:
    """Net Present Value at constant discount rate d_r."""
    _validate_finite_number("discount rate", d_r)
    _validate_flows(flows)
    try:
        return npf.npv(d_r, flows)
    except Exception as exc:
        raise SimulationComputationError(f"Failed to compute NPV: {exc}") from exc


def PBP(flows: list, loan: bool = False, loan_term: int = 0) -> float:
    """Simple (undiscounted) Payback Period in years, linearly interpolated."""
    _validate_flows(flows)
    try:
        investment = float(flows[0]) * -1
        if investment <= 0:
            return np.nan

        total = 0.0
        previous_total = 0.0
        years = 0
        max_years = 100

        for i in range(1, max_years + 1):
            fl = float(flows[i]) if i < len(flows) else float(flows[-1])
            previous_total = total
            total += fl
            years += 1
            if total >= investment:
                break
        else:
            return np.nan

        remaining = investment - previous_total
        current_year_cf = total - previous_total
        pbp = float(years - 1) + (float(remaining) / float(current_year_cf)) if current_year_cf != 0 else float(years)

        if loan and not np.isnan(pbp) and pbp < loan_term:
            pbp = float(loan_term)
        return pbp
    except FinancialSimulationError:
        raise
    except Exception as exc:
        raise SimulationComputationError(f"Failed to compute PBP: {exc}") from exc


def DPP(
    d_r: float,
    n: int,
    flows: list,
    loan: bool = False,
    loan_term: int = 0,
    max_years: int = 100,
) -> float:
    """Discounted Payback Period."""
    _validate_finite_number("discount rate", d_r)
    _validate_flows(flows)
    try:
        discounted = [flows[0]]
        for i in range(1, max_years + 1):
            cf = float(flows[i]) if i < len(flows) else float(flows[-1])
            discounted.append(cf * np.power(1 + float(d_r), -i))
            if sum(discounted) >= 0:
                break
        dpp = PBP(discounted)
        if loan and not np.isnan(dpp) and dpp < loan_term:
            dpp = float(loan_term)
        return dpp
    except FinancialSimulationError:
        raise
    except Exception as exc:
        raise SimulationComputationError(f"Failed to compute DPP: {exc}") from exc


def ROI(flows: list) -> float:
    """Return on Investment: (net profit - investment) / investment."""
    _validate_flows(flows)
    initial_investment = -float(flows[0])
    if initial_investment == 0:
        return np.nan
    net_profit = sum(float(v) for v in flows[1:])
    return (net_profit - initial_investment) / initial_investment


# ─────────────────────────────────────────────────────────────────────────────
# Cash-flow functions -- 12 financing schemes
# ─────────────────────────────────────────────────────────────────────────────
# All functions return (flows, inflows, outflows) -- length = project_lifetime + 1.
# Index 0 is Year 0 (investment/setup); indices 1..T are operating years.
# Rate inputs (fixed_interest, p_ESCO, royalty_rate, fee_plat, share_crowd)
# are expressed as fractions (e.g. 0.05 for 5%).
# ─────────────────────────────────────────────────────────────────────────────

def cash_flows(
    capex: float,
    annual_energy_savings: float,
    annual_maintenace_cost: float,
    project_lifetime: int,
    electricity_prices: list,
    inflation_rate: list,
) -> tuple:
    """Family 1 -- Equity-only."""
    try:
        flows = [-capex]
        inflows = [0.0]
        outflows = [capex]
        cumulative_infl = 1.0
        for k in range(project_lifetime):
            cumulative_infl *= (1 + inflation_rate[k] / 100.0)
            revenue = annual_energy_savings * electricity_prices[k]
            om_t = annual_maintenace_cost * cumulative_infl
            inflows.append(revenue)
            outflows.append(om_t)
            flows.append(revenue - om_t)
        return flows, inflows, outflows
    except Exception as exc:
        raise SimulationComputationError(f"cash_flows failed: {exc}") from exc


def cash_flows_with_loan(
    capex: float,
    annual_energy_savings: float,
    annual_maintenace_cost: float,
    project_lifetime: int,
    electricity_prices: list,
    inflation_rate: list,
    loan_amount: float,
    loan_interest_rate: list,
    term_years: int,
) -> tuple:
    """Family 1 -- Bank loan (amortising, variable rate)."""
    try:
        flows = [-(capex - loan_amount)]
        inflows = [loan_amount]
        outflows = [capex]
        outstanding = loan_amount
        principal = loan_amount / term_years if term_years > 0 else 0.0
        cumulative_infl = 1.0
        for year in range(project_lifetime):
            cumulative_infl *= (1 + inflation_rate[year] / 100.0)
            revenue = annual_energy_savings * electricity_prices[year]
            om_t = annual_maintenace_cost * cumulative_infl
            if year < term_years and loan_amount > 0:
                interest = outstanding * (loan_interest_rate[year] / 100.0)
                D_t = principal + interest
                outstanding -= principal
            else:
                D_t = 0.0
            inflows.append(revenue)
            outflows.append(om_t + D_t)
            flows.append(revenue - om_t - D_t)
        return flows, inflows, outflows
    except Exception as exc:
        raise SimulationComputationError(f"cash_flows_with_loan failed: {exc}") from exc


def cash_flows_green_bond_loan(
    capex: float,
    annual_energy_savings: float,
    annual_maintenace_cost: float,
    project_lifetime: int,
    electricity_prices: list,
    inflation_rate: list,
    gb_proceeds: float,
    term_years: int,
    fixed_interest: float,
    OM_green: float,
) -> tuple:
    """Family 1 -- Green bond with amortising repayment. fixed_interest is a fraction."""
    try:
        flows = [-(capex - gb_proceeds)]
        inflows = [gb_proceeds]
        outflows = [capex]
        outstanding = gb_proceeds
        principal = gb_proceeds / term_years if term_years > 0 else 0.0
        cumulative_infl = 1.0
        for t in range(1, project_lifetime + 1):
            idx = t - 1
            cumulative_infl *= (1 + inflation_rate[idx] / 100.0)
            om_t = annual_maintenace_cost * cumulative_infl
            om_green_t = OM_green * cumulative_infl
            revenue = annual_energy_savings * electricity_prices[idx]
            if t <= term_years:
                D_t = principal + outstanding * fixed_interest
                outstanding -= principal
            else:
                D_t = 0.0
            inflows.append(revenue)
            outflows.append(om_t + om_green_t + D_t)
            flows.append(revenue - om_t - om_green_t - D_t)
        return flows, inflows, outflows
    except Exception as exc:
        raise SimulationComputationError(f"cash_flows_green_bond_loan failed: {exc}") from exc


def cash_flows_green_bond_bullet(
    capex: float,
    annual_energy_savings: float,
    annual_maintenace_cost: float,
    project_lifetime: int,
    electricity_prices: list,
    inflation_rate: list,
    gb_proceeds: float,
    term_years: int,
    fixed_interest: float,
    OM_green: float,
) -> tuple:
    """Family 1 -- Green bond with bullet repayment. fixed_interest is a fraction."""
    try:
        flows = [-(capex - gb_proceeds)]
        inflows = [gb_proceeds]
        outflows = [capex]
        outstanding = gb_proceeds
        cumulative_infl = 1.0
        for t in range(1, project_lifetime + 1):
            idx = t - 1
            cumulative_infl *= (1 + inflation_rate[idx] / 100.0)
            om_t = annual_maintenace_cost * cumulative_infl
            om_green_t = OM_green * cumulative_infl
            revenue = annual_energy_savings * electricity_prices[idx]
            if t < term_years:
                D_t = outstanding * fixed_interest
            elif t == term_years:
                D_t = outstanding * fixed_interest + outstanding
                outstanding = 0.0
            else:
                D_t = 0.0
            inflows.append(revenue)
            outflows.append(om_t + om_green_t + D_t)
            flows.append(revenue - om_t - om_green_t - D_t)
        return flows, inflows, outflows
    except Exception as exc:
        raise SimulationComputationError(f"cash_flows_green_bond_bullet failed: {exc}") from exc


def cash_flows_on_bill_financing(
    capex: float,
    annual_energy_savings: float,
    annual_maintenace_cost: float,
    project_lifetime: int,
    electricity_prices: list,
    inflation_rate: list,
    term_years: int,
    fixed_interest: float,
) -> tuple:
    """Family 2 -- On-bill financing. fixed_interest is a fraction."""
    flows = [0.0]
    inflows = [0.0]
    outflows = [0.0]
    outstanding = capex
    principal = capex / term_years if term_years > 0 else 0.0
    cumulative_infl = 1.0
    for t in range(1, project_lifetime + 1):
        idx = t - 1
        cumulative_infl *= (1 + inflation_rate[idx] / 100.0)
        om_t = annual_maintenace_cost * cumulative_infl
        revenue = annual_energy_savings * electricity_prices[idx]
        if t <= term_years:
            D_t = principal + outstanding * fixed_interest
            outstanding -= principal
        else:
            D_t = 0.0
        inflows.append(revenue)
        outflows.append(om_t + D_t)
        flows.append(revenue - om_t - D_t)
    return flows, inflows, outflows


def cash_flows_operational_leasing(
    annual_energy_savings: float,
    project_lifetime: int,
    electricity_prices: list,
    lease_payment: float,
    term_years: int,
) -> tuple:
    """Family 2 -- Operational lease (O&M included in lease)."""
    flows = [0.0]
    inflows = [0.0]
    outflows = [0.0]
    for t in range(1, project_lifetime + 1):
        idx = t - 1
        revenue = annual_energy_savings * electricity_prices[idx]
        D_t = lease_payment if t <= term_years else 0.0
        inflows.append(revenue)
        outflows.append(D_t)
        flows.append(revenue - D_t)
    return flows, inflows, outflows


def cash_flows_epc_shared_savings(
    annual_energy_savings: float,
    annual_maintenace_cost: float,
    project_lifetime: int,
    electricity_prices: list,
    inflation_rate: list,
    p_ESCO: float,
    term_years: int,
) -> tuple:
    """Family 2 -- EPC shared savings. p_ESCO is the fraction paid to ESCO."""
    flows = [0.0]
    inflows = [0.0]
    outflows = [0.0]
    cumulative_infl = 1.0
    for t in range(1, project_lifetime + 1):
        idx = t - 1
        cumulative_infl *= (1 + inflation_rate[idx] / 100.0)
        om_t = annual_maintenace_cost * cumulative_infl
        AS_t = annual_energy_savings * electricity_prices[idx]
        D_t = AS_t * p_ESCO if t <= term_years else 0.0
        inflows.append(AS_t)
        outflows.append(om_t + D_t)
        flows.append(AS_t - om_t - D_t)
    return flows, inflows, outflows


def cash_flows_first_out_contract(
    capex: float,
    annual_energy_savings: float,
    annual_maintenace_cost: float,
    project_lifetime: int,
    electricity_prices: list,
    inflation_rate: list,
) -> tuple:
    """Family 2 -- EPC first-out (ESCO recoups CAPEX from all savings)."""
    flows = [0.0]
    inflows = [0.0]
    outflows = [0.0]
    D_paid = 0.0
    cumulative_infl = 1.0
    for t in range(1, project_lifetime + 1):
        idx = t - 1
        cumulative_infl *= (1 + inflation_rate[idx] / 100.0)
        om_t = annual_maintenace_cost * cumulative_infl
        AS_t = annual_energy_savings * electricity_prices[idx]
        op_cf = AS_t - om_t
        remaining = capex - D_paid
        if remaining <= 0:
            D_t = 0.0
        else:
            D_t = min(max(0.0, op_cf), remaining)
            D_paid += D_t
        inflows.append(AS_t)
        outflows.append(om_t + D_t)
        flows.append(op_cf - D_t)
    return flows, inflows, outflows


def cash_flows_epc_guaranteed_savings(
    capex: float,
    annual_energy_savings: float,
    annual_maintenace_cost: float,
    project_lifetime: int,
    electricity_prices: list,
    inflation_rate: list,
    loan_interest_rate: list,
    term_years: int,
    gs: float,
) -> tuple:
    """Family 2 -- EPC guaranteed savings. gs is guaranteed savings in EUR/year (today's money)."""
    flows = [0.0]
    inflows = [capex]
    outflows = [capex]
    outstanding = capex
    principal = capex / term_years if term_years > 0 else 0.0
    cumulative_infl = 1.0
    for t in range(1, project_lifetime + 1):
        idx = t - 1
        cumulative_infl *= (1 + inflation_rate[idx] / 100.0)
        om_t = annual_maintenace_cost * cumulative_infl
        gs_t = gs * cumulative_infl
        AS_t = annual_energy_savings * electricity_prices[idx]
        if t <= term_years:
            interest = outstanding * (loan_interest_rate[idx] / 100.0)
            D_t = principal + interest
            outstanding -= principal
        else:
            D_t = 0.0
        comp = max(0.0, gs_t - AS_t)
        inflows.append(AS_t + comp)
        outflows.append(om_t + D_t)
        flows.append(AS_t - om_t - D_t + comp)
    return flows, inflows, outflows


def cash_flows_lending_crowdfunding(
    capex: float,
    annual_energy_savings: float,
    annual_maintenace_cost: float,
    project_lifetime: int,
    electricity_prices: list,
    inflation_rate: list,
    loan_crowd: float,
    fixed_interest: float,
    term_years: int,
    fee_plat: float,
) -> tuple:
    """Family 3 -- Lending crowdfunding. fixed_interest and fee_plat are fractions."""
    plat_cost = loan_crowd * fee_plat
    flows = [loan_crowd - plat_cost - capex]
    inflows = [loan_crowd]
    outflows = [plat_cost + capex]
    r = fixed_interest
    if term_years > 0 and r > 0:
        debt_payment = loan_crowd * (r * (1 + r) ** term_years) / ((1 + r) ** term_years - 1)
    elif term_years > 0:
        debt_payment = loan_crowd / term_years
    else:
        debt_payment = 0.0
    cumulative_infl = 1.0
    for t in range(1, project_lifetime + 1):
        idx = t - 1
        cumulative_infl *= (1 + inflation_rate[idx] / 100.0)
        om_t = annual_maintenace_cost * cumulative_infl
        AS_t = annual_energy_savings * electricity_prices[idx]
        D_t = debt_payment if t <= term_years else 0.0
        inflows.append(AS_t)
        outflows.append(om_t + D_t)
        flows.append(AS_t - om_t - D_t)
    return flows, inflows, outflows


def cash_flows_royalty_crowdfunding(
    capex: float,
    annual_energy_savings: float,
    annual_maintenace_cost: float,
    project_lifetime: int,
    electricity_prices: list,
    inflation_rate: list,
    loan_crowd: float,
    royalty_rate: float,
    term_years: int,
    fee_plat: float,
) -> tuple:
    """Family 3 -- Royalty crowdfunding. royalty_rate and fee_plat are fractions."""
    plat_cost = loan_crowd * fee_plat
    flows = [loan_crowd - plat_cost - capex]
    inflows = [loan_crowd]
    outflows = [plat_cost + capex]
    cumulative_infl = 1.0
    for t in range(1, project_lifetime + 1):
        idx = t - 1
        cumulative_infl *= (1 + inflation_rate[idx] / 100.0)
        om_t = annual_maintenace_cost * cumulative_infl
        revenue = annual_energy_savings * electricity_prices[idx]
        pay_crowd = revenue * royalty_rate if t <= term_years else 0.0
        inflows.append(revenue)
        outflows.append(pay_crowd + om_t)
        flows.append(revenue - pay_crowd - om_t)
    return flows, inflows, outflows


def cash_flows_equity_crowdfunding(
    capex: float,
    annual_energy_savings: float,
    annual_maintenace_cost: float,
    project_lifetime: int,
    electricity_prices: list,
    inflation_rate: list,
    equity_crowd: float,
    share_crowd: float,
    fee_plat: float,
) -> tuple:
    """Family 3 -- Equity crowdfunding. share_crowd and fee_plat are fractions."""
    try:
        plat_cost = equity_crowd * fee_plat
        flows = [equity_crowd - plat_cost - capex]
        inflows = [equity_crowd]
        outflows = [plat_cost + capex]
        cumulative_infl = 1.0
        for t in range(1, project_lifetime + 1):
            idx = t - 1
            cumulative_infl *= (1.0 + inflation_rate[idx] / 100.0)
            revenue = annual_energy_savings * electricity_prices[idx]
            costs = annual_maintenace_cost * cumulative_infl
            distributable = revenue - costs
            dev_cf = distributable * (1 - share_crowd) if distributable > 0 else 0.0
            crowd_cf = distributable - dev_cf if distributable > 0 else 0.0
            inflows.append(revenue)
            outflows.append(costs + crowd_cf)
            flows.append(dev_cf)
        return flows, inflows, outflows
    except Exception as exc:
        raise SimulationComputationError(f"cash_flows_equity_crowdfunding failed: {exc}") from exc


# ─────────────────────────────────────────────────────────────────────────────
# Scheme dispatch registry
# ─────────────────────────────────────────────────────────────────────────────

CASHFLOW_FUNCTIONS: dict = {
    "equity":                  cash_flows,
    "bank_loan":               cash_flows_with_loan,
    "green_bond_loan":         cash_flows_green_bond_loan,
    "green_bond_bullet":       cash_flows_green_bond_bullet,
    "on_bill":                 cash_flows_on_bill_financing,
    "operational_lease":       cash_flows_operational_leasing,
    "epc_shared_savings":      cash_flows_epc_shared_savings,
    "epc_first_out":           cash_flows_first_out_contract,
    "epc_guaranteed_savings":  cash_flows_epc_guaranteed_savings,
    "lending_crowdfunding":    cash_flows_lending_crowdfunding,
    "royalty_crowdfunding":    cash_flows_royalty_crowdfunding,
    "equity_crowdfunding":     cash_flows_equity_crowdfunding,
}

SCHEME_FAMILY: dict = {
    "equity":                  "self_financed",
    "bank_loan":               "debt_financed",
    "green_bond_loan":         "debt_financed",
    "green_bond_bullet":       "debt_financed",
    "on_bill":                 "esco_zero_capex",
    "operational_lease":       "esco_zero_capex",
    "epc_shared_savings":      "esco_zero_capex",
    "epc_first_out":           "esco_zero_capex",
    "epc_guaranteed_savings":  "esco_zero_capex",
    "lending_crowdfunding":    "crowdfunding",
    "royalty_crowdfunding":    "crowdfunding",
    "equity_crowdfunding":     "crowdfunding",
}


def _scheme_builder(scheme_type: str, details: dict, ctx: dict) -> dict:
    """Build base_inputs dict for a scheme from context and user-supplied details."""
    common = {
        "capex":                  ctx["capex"],
        "annual_energy_savings":  ctx["annual_energy_savings"],
        "annual_maintenace_cost": ctx["annual_maintenace_cost"],
        "project_lifetime":       ctx["project_lifetime"],
        "electricity_prices":     None,
        "inflation_rate":         None,
    }

    if scheme_type == "equity":
        return common

    if scheme_type == "bank_loan":
        return {**common, "loan_amount": float(details["loan_amount"]), "loan_interest_rate": None, "term_years": int(details["term_years"])}

    if scheme_type == "green_bond_loan":
        return {**common, "gb_proceeds": float(details["gb_proceeds"]), "term_years": int(details["term_years"]), "fixed_interest": float(details["fixed_interest"]), "OM_green": float(details["OM_green"])}

    if scheme_type == "green_bond_bullet":
        return {**common, "gb_proceeds": float(details["gb_proceeds"]), "term_years": int(details["term_years"]), "fixed_interest": float(details["fixed_interest"]), "OM_green": float(details["OM_green"])}

    if scheme_type == "on_bill":
        return {**common, "term_years": int(details["term_years"]), "fixed_interest": float(details["fixed_interest"])}

    if scheme_type == "operational_lease":
        return {
            "annual_energy_savings": ctx["annual_energy_savings"],
            "project_lifetime":      ctx["project_lifetime"],
            "electricity_prices":    None,
            "lease_payment":         float(details["lease_payment"]),
            "term_years":            int(details["term_years"]),
        }

    if scheme_type == "epc_shared_savings":
        return {
            "annual_energy_savings":  ctx["annual_energy_savings"],
            "annual_maintenace_cost": ctx["annual_maintenace_cost"],
            "project_lifetime":       ctx["project_lifetime"],
            "electricity_prices":     None,
            "inflation_rate":         None,
            "p_ESCO":                 float(details["p_ESCO"]),
            "term_years":             int(details["term_years"]),
        }

    if scheme_type == "epc_first_out":
        return common

    if scheme_type == "epc_guaranteed_savings":
        return {**common, "loan_interest_rate": None, "term_years": int(details["term_years"]), "gs": float(details["gs"])}

    if scheme_type == "lending_crowdfunding":
        return {**common, "loan_crowd": float(details["loan_crowd"]), "fixed_interest": float(details["fixed_interest"]), "term_years": int(details["term_years"]), "fee_plat": float(details["fee_plat"])}

    if scheme_type == "royalty_crowdfunding":
        return {**common, "loan_crowd": float(details["loan_crowd"]), "royalty_rate": float(details["royalty_rate"]), "term_years": int(details["term_years"]), "fee_plat": float(details["fee_plat"])}

    if scheme_type == "equity_crowdfunding":
        return {**common, "equity_crowd": float(details["equity_crowd"]), "share_crowd": float(details["share_crowd"]), "fee_plat": float(details["fee_plat"])}

    raise SchemeConfigurationError(f"Unsupported scheme type: {scheme_type!r}")


def create_scheme_definitions(
    *,
    capex: float,
    annual_energy_savings: float,
    annual_maintenace_cost: float,
    project_lifetime: int,
    schemes: list,
) -> list:
    """Create scheme definitions from (scheme_type, details) tuples."""
    ctx = {
        "capex":                  float(capex),
        "annual_energy_savings":  float(annual_energy_savings),
        "annual_maintenace_cost": float(annual_maintenace_cost),
        "project_lifetime":       int(project_lifetime),
    }
    definitions = []
    for idx, (scheme_type, details) in enumerate(schemes, start=1):
        if scheme_type not in CASHFLOW_FUNCTIONS:
            raise SchemeConfigurationError(f"Unsupported scheme type: {scheme_type!r}")
        definitions.append({
            "scheme_id":         idx,
            "scheme_type":       scheme_type,
            "scheme_family":     SCHEME_FAMILY[scheme_type],
            "cashflow_function": CASHFLOW_FUNCTIONS[scheme_type],
            "base_inputs":       _scheme_builder(scheme_type, details, ctx),
        })
    return definitions


def prepare_cashflow_inputs(
    base_inputs: dict,
    electricity_prices: list,
    inflation_rate: list,
    loan_interest_rate: list | None = None,
    annual_energy_savings: float | None = None,
) -> dict:
    """Inject Monte Carlo sampled market variables into a scheme's base inputs."""
    inputs = dict(base_inputs)
    if "annual_energy_savings" in inputs and annual_energy_savings is not None:
        inputs["annual_energy_savings"] = float(annual_energy_savings)
    if "electricity_prices" in inputs:
        inputs["electricity_prices"] = electricity_prices
    if "inflation_rate" in inputs:
        inputs["inflation_rate"] = inflation_rate
    if "loan_interest_rate" in inputs:
        lifetime = int(inputs.get("project_lifetime", len(electricity_prices)))
        inputs["loan_interest_rate"] = loan_interest_rate if loan_interest_rate is not None else [0.0] * lifetime
    return inputs


# ─────────────────────────────────────────────────────────────────────────────
# Main Monte Carlo runner
# ─────────────────────────────────────────────────────────────────────────────

def get_kpi_results(
    *,
    capex: float,
    annual_energy_savings: float,
    annual_maintenace_cost: float,
    project_lifetime: int,
    schemes: list,
    n_sims: int = 10000,
    seed: int = 42,
) -> dict:
    """
    Run Monte Carlo KPI simulation for all requested financing schemes.

    Parameters
    ----------
    capex : float
        Total capital expenditure (EUR).
    annual_energy_savings : float
        Base estimate of annual energy saved (kWh/year).
    annual_maintenace_cost : float
        Annual O&M cost in today's money (EUR/year).
    project_lifetime : int
        Evaluation horizon (years, max 30).
    schemes : list of (scheme_type, details) tuples
        scheme_type must be a key in CASHFLOW_FUNCTIONS.
    n_sims : int
        Number of Monte Carlo draws (default 10 000).
    seed : int
        Random seed for reproducibility.

    Returns
    -------
    dict
        Keys are scheme_type strings. Each value contains:
        scheme_id, scheme_family, summary, kpi_histograms, cashflow_distributions.
    """
    _ensure(capex > 0,                   "capex must be positive.")
    _ensure(annual_energy_savings > 0,   "annual_energy_savings must be positive.")
    _ensure(annual_maintenace_cost >= 0, "annual_maintenace_cost must be non-negative.")
    _ensure(1 <= project_lifetime <= 30, "project_lifetime must be between 1 and 30.")
    _ensure(0 < n_sims <= 1_000_000,     "n_sims must be between 1 and 1,000,000.")

    scheme_definitions = create_scheme_definitions(
        capex=capex,
        annual_energy_savings=annual_energy_savings,
        annual_maintenace_cost=annual_maintenace_cost,
        project_lifetime=project_lifetime,
        schemes=schemes,
    )
    if not scheme_definitions:
        raise ExperimentConfigurationError("No scheme definitions provided.")

    T = project_lifetime

    # ── Market scenario calibration ───────────────────────────────────────────
    inflation_rate_data = {
        "optimistic":  pad_to_length([2.8,2.4,2.2,2.0,2.0,2.0,2.0,2.0,2.0,2.0, 2.0,2.0,2.0,2.0,2.0,2.0,2.0,2.0,2.0,2.0, 2.0,2.0,2.0,2.0,2.0,2.0,2.0,2.0,2.0,2.0], T),
        "moderate":    pad_to_length([3.0,2.7,2.5,2.4,2.3,2.3,2.4,2.4,2.5,2.5, 2.4,2.4,2.3,2.3,2.3,2.3,2.3,2.3,2.3,2.3, 2.2,2.2,2.2,2.2,2.2,2.2,2.2,2.2,2.2,2.2], T),
        "pessimistic": pad_to_length([3.5,3.3,3.2,3.0,2.9,2.8,2.9,3.0,3.1,3.2, 3.2,3.2,3.1,3.1,3.0,3.0,3.0,3.0,2.9,2.9, 2.8,2.8,2.7,2.7,2.7,2.6,2.6,2.6,2.5,2.5], T),
    }
    electricity_prices_data = {
        "pessimistic": pad_to_length([0.221,0.229,0.237,0.245,0.253,0.261,0.269,0.277,0.285,0.293, 0.301,0.310,0.318,0.326,0.334,0.342,0.350,0.358], T),
        "moderate":    pad_to_length([0.246,0.254,0.262,0.270,0.278,0.286,0.294,0.302,0.310,0.318, 0.326,0.335,0.343,0.351,0.359,0.367,0.375,0.383], T),
        "optimistic":  pad_to_length([0.271,0.279,0.287,0.295,0.303,0.311,0.319,0.327,0.335,0.343, 0.351,0.360,0.368,0.376,0.384,0.392,0.400,0.408], T),
    }
    interest_rate_data = {
        "optimistic":  pad_to_length([2.5,2.8,3.0,3.0,2.9,2.8,2.8,2.7,2.7,2.7, 2.6,2.6,2.6,2.5,2.5,2.5,2.5,2.5,2.5,2.5, 2.5,2.5,2.5,2.5,2.5,2.5,2.5,2.5,2.5,2.5], T),
        "moderate":    pad_to_length([3.5,3.8,4.0,4.0,3.9,3.8,3.8,3.7,3.7,3.7, 3.6,3.6,3.6,3.5,3.5,3.5,3.5,3.5,3.5,3.5, 3.5,3.5,3.5,3.5,3.5,3.5,3.5,3.5,3.5,3.5], T),
        "pessimistic": pad_to_length([5.0,5.3,5.5,5.5,5.4,5.3,5.3,5.2,5.2,5.2, 5.1,5.1,5.0,5.0,5.0,5.0,5.0,5.0,5.0,5.0, 5.0,5.0,5.0,5.0,5.0,5.0,5.0,5.0,5.0,5.0], T),
    }
    discount_rate_data = {"optimistic": [0.03], "moderate": [0.05], "pessimistic": [0.07]}

    dist_params = build_market_distributions(
        inflation_rate_data=inflation_rate_data,
        electricity_prices_data=electricity_prices_data,
        interest_rate_data=interest_rate_data,
        discount_rate_data=discount_rate_data,
        project_lifetime=T,
    )

    # ── Monte Carlo draws ─────────────────────────────────────────────────────
    rng = np.random.default_rng(seed)
    infl = rng.normal(dist_params["inflation"]["mu"],  dist_params["inflation"]["sigma"],  size=(n_sims, T))
    rate = rng.normal(dist_params["loan_rate"]["mu"],  dist_params["loan_rate"]["sigma"],  size=(n_sims, T))
    disc = rng.normal(dist_params["discount"]["mu"],   dist_params["discount"]["sigma"],   size=(n_sims, T))
    elec = np.exp(rng.normal(dist_params["elec_price"]["mu_ln"], dist_params["elec_price"]["sigma_ln"], size=(n_sims, T)))

    es_dist = build_energy_savings_factor_distribution()
    energy_savings_factor = rng.normal(es_dist["mu"], es_dist["sigma"], size=n_sims)

    infl  = np.maximum(infl,  -50.0)
    rate  = np.maximum(rate,    0.0)
    disc  = np.maximum(disc,  -0.99)
    elec  = np.maximum(elec,   1e-9)
    energy_savings_factor = np.maximum(energy_savings_factor, 0.0)

    # ── Per-scheme simulation ─────────────────────────────────────────────────
    results: dict = {}

    for scheme_def in scheme_definitions:
        scheme_type       = scheme_def["scheme_type"]
        scheme_family     = scheme_def["scheme_family"]
        cashflow_function = scheme_def["cashflow_function"]
        base_inputs       = scheme_def["base_inputs"]

        irr             = np.full(n_sims, np.nan)
        npv_arr         = np.full(n_sims, np.nan)
        pbp_arr         = np.full(n_sims, np.nan)
        dpp_arr         = np.full(n_sims, np.nan)
        roi_arr         = np.full(n_sims, np.nan)
        total_repayment = np.full(n_sims, np.nan)
        cashflow_paths  = np.full((n_sims, T + 1), np.nan)
        inflow_paths    = np.full((n_sims, T + 1), np.nan)
        outflow_paths   = np.full((n_sims, T + 1), np.nan)

        base_es = float(base_inputs.get("annual_energy_savings", annual_energy_savings))

        for i in range(n_sims):
            inputs_i = prepare_cashflow_inputs(
                base_inputs=base_inputs,
                electricity_prices=elec[i].tolist(),
                inflation_rate=infl[i].tolist(),
                loan_interest_rate=rate[i].tolist(),
                annual_energy_savings=base_es * float(energy_savings_factor[i]),
            )
            try:
                flows, inflows_i, outflows_i = cashflow_function(**inputs_i)
                _validate_flows(flows)

                irr[i]         = IRR(flows)
                npv_arr[i]     = NPV(float(disc[i, 0]), flows)
                has_term       = "term_years" in inputs_i and inputs_i["term_years"]
                pbp_arr[i]     = PBP(flows, loan=bool(has_term), loan_term=int(inputs_i.get("term_years", 0)))
                dpp_arr[i]     = DPP(float(disc[i, 0]), T, flows, loan=bool(has_term), loan_term=int(inputs_i.get("term_years", 0)))
                roi_arr[i]     = ROI(flows)
                total_repayment[i] = float(np.sum(np.asarray(outflows_i[1:], dtype=float)))

                cashflow_paths[i, :] = np.asarray(flows, dtype=float)
                inflow_paths[i, :]   = np.asarray(inflows_i, dtype=float)
                outflow_paths[i, :]  = np.asarray(outflows_i, dtype=float)
            except FinancialSimulationError:
                raise
            except Exception as exc:
                raise SimulationComputationError(
                    f"Simulation failed for '{scheme_type}' at iteration {i}: {exc}"
                ) from exc

        censor = T + 1
        pbp_censored = np.where(~np.isfinite(pbp_arr) | (pbp_arr > T), censor, pbp_arr)
        dpp_censored = np.where(~np.isfinite(dpp_arr) | (dpp_arr > T), censor, dpp_arr)
        disc_target = float(np.nanmedian(disc[:, 0]))

        def pct(a, qs=(5, 10, 25, 50, 75, 90, 95)):
            return {f"P{q}": float(np.nanpercentile(a, q)) for q in qs}

        def pct_by_year(paths, qs=(5, 10, 25, 50, 75, 90, 95)):
            arr = np.asarray(paths, dtype=float)
            return {f"P{q}": np.nanpercentile(arr, q, axis=0).tolist() for q in qs}

        def pr(mask):
            return float(np.nanmean(np.asarray(mask, dtype=bool)))

        results[scheme_type] = {
            "scheme_id":     scheme_def["scheme_id"],
            "scheme_family": scheme_family,
            "summary": {
                "percentiles": {
                    "IRR":             pct(irr),
                    "NPV":             pct(npv_arr),
                    "PBP":             pct(pbp_censored),
                    "DPP":             pct(dpp_censored),
                    "ROI":             pct(roi_arr),
                    "total_repayment": pct(total_repayment),
                },
                "probabilities": {
                    "Pr(NPV > 0)":          pr(npv_arr > 0),
                    f"Pr(PBP < {T}y)":      pr(pbp_arr < T),
                    f"Pr(DPP < {T}y)":      pr(dpp_arr < T),
                },
                "disc_target_used": disc_target,
                "n_sims":           n_sims,
            },
            "kpi_histograms": {
                "NPV": _build_kpi_histogram_payload("NPV", npv_arr),
                "IRR": _build_kpi_histogram_payload("IRR", irr),
                "ROI": _build_kpi_histogram_payload("ROI", roi_arr),
                "PBP": _build_kpi_histogram_payload("PBP", pbp_arr, project_lifetime=T),
                "DPP": _build_kpi_histogram_payload("DPP", dpp_arr, project_lifetime=T),
            },
            "cashflow_distributions": {
                "years":      list(range(T + 1)),
                "cash_flows": pct_by_year(cashflow_paths),
                "inflows":    pct_by_year(inflow_paths),
                "outflows":   pct_by_year(outflow_paths),
            },
        }

    return results

"""
Updated financial simulation script.

Run:
    pip install numpy numpy-financial
    python financial_simulation_standalone.py

"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Callable

import numpy as np
import numpy_financial as npf

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


class ResultPersistenceError(FinancialSimulationError):
    """Raised when simulation results cannot be saved."""


def _ensure(condition: bool, message: str, exc_type: type[Exception] = FinancialInputError) -> None:
    if not condition:
        raise exc_type(message)


def _is_finite_number(value: Any) -> bool:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return False
    return math.isfinite(numeric)


def _validate_finite_number(name: str, value: Any, allow_none: bool = False) -> None:
    if value is None and allow_none:
        return
    _ensure(_is_finite_number(value), f"{name} must be a finite number. Got: {value!r}")


def _validate_non_negative_integer(name: str, value: Any, *, allow_zero: bool = True) -> int:
    try:
        ivalue = int(value)
    except (TypeError, ValueError):
        raise FinancialInputError(f"{name} must be an integer. Got: {value!r}")

    if allow_zero:
        _ensure(ivalue >= 0, f"{name} must be >= 0. Got: {ivalue}")
    else:
        _ensure(ivalue > 0, f"{name} must be > 0. Got: {ivalue}")
    return ivalue


def _validate_series(name: str, values: Any, required_length: int) -> None:
    _ensure(isinstance(values, list), f"{name} must be a list. Got: {type(values).__name__}")
    _ensure(len(values) >= required_length, f"{name} must contain at least {required_length} values. Got: {len(values)}")
    for idx, value in enumerate(values[:required_length]):
        _ensure(_is_finite_number(value), f"{name}[{idx}] must be a finite number. Got: {value!r}")


def _validate_flows(flows: Any, *, require_initial_outflow: bool = False) -> None:
    _ensure(isinstance(flows, list), f"Cash-flow function must return a list. Got: {type(flows).__name__}", SimulationComputationError)
    _ensure(len(flows) >= 2, f"Cash-flow list must contain at least 2 values. Got: {len(flows)}", SimulationComputationError)
    for idx, value in enumerate(flows):
        _ensure(_is_finite_number(value), f"Cash-flow at index {idx} must be finite. Got: {value!r}", SimulationComputationError)
    if require_initial_outflow:
        _ensure(float(flows[0]) < 0, f"Initial cash-flow must be negative for this KPI calculation. Got: {flows[0]!r}", SimulationComputationError)

def _build_kpi_histogram_payload(
    name: str,
    values: Any,
    *,
    bins: int = 30,
    censor_value: float | None = None,
    project_lifetime: int | None = None,
) -> dict[str, Any]:
    raw = np.asarray(values, dtype=float)
    empty_payload = {
        "bin_edges": [],
        "feasible_counts": [],
        "infeasible_counts": [],
        "p10": None,
        "p50": None,
        "p90": None,
        "censor_value": float(censor_value) if censor_value is not None else None,
        "project_lifetime": int(project_lifetime) if project_lifetime is not None else None,
    }

    if name in ("PBP", "DPP"):
        a = raw[np.isfinite(raw)]
        if a.size == 0:
            return empty_payload

        if project_lifetime is not None:
            infeasible_mask = (a > float(project_lifetime))
        elif censor_value is not None:
            infeasible_mask = np.isclose(a, float(censor_value))
        else:
            infeasible_mask = np.zeros_like(a, dtype=bool)

        feasible = a[~infeasible_mask]
        infeasible = a[infeasible_mask]

        if a.size == 1 or np.isclose(a.min(), a.max()):
            center = float(a[0])
            bin_edges = np.array([max(center - 0.5, 0.0), center + 0.5], dtype=float)
        else:
            bin_edges = np.histogram_bin_edges(a, bins=bins)

        feasible_counts, _ = np.histogram(feasible, bins=bin_edges)
        infeasible_counts, _ = np.histogram(infeasible, bins=bin_edges)
        percentile_source = a
    else:
        a = raw[np.isfinite(raw)]
        if a.size == 0:
            return empty_payload

        if name in ("NPV", "IRR", "ROI"):
            infeasible_mask = (a < 0)
        else:
            infeasible_mask = np.zeros_like(a, dtype=bool)

        feasible = a[~infeasible_mask]
        infeasible = a[infeasible_mask]
        bin_edges = np.histogram_bin_edges(a, bins=bins)
        feasible_counts, _ = np.histogram(feasible, bins=bin_edges)
        infeasible_counts, _ = np.histogram(infeasible, bins=bin_edges)
        percentile_source = a

    if percentile_source.size == 0:
        p10 = p50 = p90 = None
    else:
        p10, p50, p90 = np.percentile(percentile_source, [10, 50, 90])

    return {
        "bin_edges": bin_edges.tolist(),
        "feasible_counts": feasible_counts.tolist(),
        "infeasible_counts": infeasible_counts.tolist(),
        "p10": float(p10) if p10 is not None else None,
        "p50": float(p50) if p50 is not None else None,
        "p90": float(p90) if p90 is not None else None,
        "censor_value": float(censor_value) if censor_value is not None else None,
        "project_lifetime": int(project_lifetime) if project_lifetime is not None else None,
    }


def cash_flows_operational_leasing(
    annual_energy_savings: float,
    project_lifetime: int,
    electricity_prices: list[float],
    lease_payment: float,
    term_years: int,
) -> list[float]:
    """Compute yearly net cash-flows for an **operational leasing** scheme.

    Parameters
    ----------
    annual_energy_savings : float
        Nominal number of kWh saved per year.
    project_lifetime : int
        Evaluation horizon in *years*.
    electricity_prices : list[float]
        Forecast grid prices for each year.
    lease_payment : float
        Fixed yearly lease payment.
    term_years : int
        Lease duration in *years*.

    Returns
    -------
    list[float]
        Cash-flow sequence where the first entry is ``0`` because the lessor
        covers the initial CAPEX.
    """
    flows = []
    inflows = []
    outflows = []
    # Year 0: lessor covers CAPEX
    flows.append(0)
    inflows.append(0)
    outflows.append(0)

    for t in range(1, project_lifetime + 1):
        idx = t - 1
        # Operating cash flow (lessee O&M assumed included in lease => OMt = 0)
        revenue = annual_energy_savings * electricity_prices[idx]
        op_cf = revenue

        # Lease payment
        if t <= term_years:
            D_t = lease_payment
        else:
            D_t = 0.0
        inflows.append(revenue)
        outflows.append(D_t)
        flows.append(op_cf - D_t)

    return flows, inflows, outflows

#interest is usually low
def cash_flows_on_bill_financing(
    capex: float,
    annual_energy_savings: float,
    annual_maintenace_cost: float,
    project_lifetime: int,
    electricity_prices: list[float],
    inflation_rate: list[float],
    term_years: int,
    fixed_interest: float,          # fixed predefined interest rate (e.g., 0.05 for 5%)
) -> list[float]:
    """Compute yearly net cash-flows for **on-bill financing**.

    Parameters
    ----------
    capex : float
        Up-front capital expenditure covered by the provider.
    annual_energy_savings : float
        Nominal number of kWh saved per year.
    annual_maintenace_cost : float
        Nominal yearly O&M cost in today's money.
    project_lifetime : int
        Evaluation horizon in *years*.
    electricity_prices : list[float]
        Forecast grid prices for each year.
    inflation_rate : list[float]
        Inflation rates for each year.
    term_years : int
        Repayment tenor in *years*.
    fixed_interest : float
        Fixed annual interest rate expressed as a fraction.

    Returns
    -------
    list[float]
        Cash-flow sequence where the first entry is ``0`` because the provider
        covers the initial CAPEX.
    """
    flows = []
    inflows = []
    outflows = []

    # Year 0: provider covers 100% CAPEX
    flows.append(0)
    inflows.append(0)
    outflows.append(0)

    outstanding = capex
    principal = capex / term_years if term_years > 0 else 0
    cumulative_inflation = 1.0

    for t in range(1, project_lifetime + 1):
        idx = t - 1
        cumulative_inflation *= (1 + inflation_rate[idx] / 100.0)
        om_t = annual_maintenace_cost * cumulative_inflation
        revenue = annual_energy_savings * electricity_prices[idx]
        op_cf = revenue - om_t

        # On-bill charge (debt service)
        if t <= term_years:
            interest = outstanding * fixed_interest 
            D_t = principal + interest
            outstanding -= principal
        else:
            D_t = 0.0

        inflows.append(revenue)
        outflows.append(om_t + D_t)
        flows.append(op_cf - D_t)

    return flows, inflows, outflows


def cash_flows_green_bond_loan(
    capex: float,
    annual_energy_savings: float,
    annual_maintenace_cost: float,
    project_lifetime: int,
    electricity_prices: list[float],
    inflation_rate: list[float],
    gb_proceeds: float,
    term_years: int,
    fixed_interest: float,         # fixed predefined interest rate (e.g., 0.05 for 5%)
    OM_green: float,
) -> list[float]:
    """Compute yearly net cash-flows for a **green bond with amortising loan**.

    Parameters
    ----------
    capex : float
        Up-front capital expenditure.
    annual_energy_savings : float
        Nominal number of kWh saved per year.
    annual_maintenace_cost : float
        Nominal yearly base O&M cost in today's money.
    project_lifetime : int
        Evaluation horizon in *years*.
    electricity_prices : list[float]
        Forecast grid prices for each year.
    inflation_rate : list[float]
        Inflation rates for each year.
    gb_proceeds : float
        Amount raised through the green bond at *t = 0*.
    term_years : int
        Repayment tenor in *years*.
    fixed_interest : float
        Fixed annual interest rate expressed as a fraction.
    OM_green : float
        Additional yearly O&M cost associated with the green bond structure.

    Returns
    -------
    list[float]
        Cash-flow sequence where the first entry is the residual equity outflow
        after deducting green bond proceeds.
    """
    flows = []
    inflows = []
    outflows = []
    cf = -(capex - gb_proceeds)
    flows.append(cf)
    inflows.append(gb_proceeds)
    outflows.append(capex)

    outstanding = gb_proceeds
    principal = gb_proceeds / term_years
    cumulative_inflation = 1.0

    for t in range(1, project_lifetime + 1):
        idx = t - 1
        cumulative_inflation *= (1 + inflation_rate[idx] / 100.0)
        om_t = annual_maintenace_cost * cumulative_inflation
        om_green_t = OM_green * cumulative_inflation
        revenue = annual_energy_savings * electricity_prices[idx]
        op_cf = revenue - (om_t + om_green_t)

        # Debt service (constant principal)
        if t <= term_years:
            interest = outstanding * fixed_interest 
            D_t = principal + interest
            outstanding -= principal
        else:
            D_t = 0.0
        inflows.append(revenue)
        outflows.append(om_t + om_green_t + D_t)
        flows.append(op_cf - D_t)

    return flows, inflows, outflows

def cash_flows_green_bond_bullet(
    capex: float,
    annual_energy_savings: float,
    annual_maintenace_cost: float,
    project_lifetime: int,
    electricity_prices: list[float],
    inflation_rate: list[float],
    gb_proceeds: float,
    term_years: int,
    fixed_interest: float,  # fixed predefined interest rate (e.g., 0.05 for 5%)
    OM_green: float,
) -> list[float]:
    """Compute yearly net cash-flows for a **green bond with bullet repayment**.

    Parameters
    ----------
    capex : float
        Up-front capital expenditure.
    annual_energy_savings : float
        Nominal number of kWh saved per year.
    annual_maintenace_cost : float
        Nominal yearly base O&M cost in today's money.
    project_lifetime : int
        Evaluation horizon in *years*.
    electricity_prices : list[float]
        Forecast grid prices for each year.
    inflation_rate : list[float]
        Inflation rates for each year.
    gb_proceeds : float
        Amount raised through the green bond at *t = 0*.
    term_years : int
        Bond maturity in *years*.
    fixed_interest : float
        Fixed annual interest rate expressed as a fraction.
    OM_green : float
        Additional yearly O&M cost associated with the green bond structure.

    Returns
    -------
    list[float]
        Cash-flow sequence where the first entry is the residual equity outflow
        after deducting green bond proceeds.
    """
    flows = []
    inflows = []
    outflows = []
    cf = -(capex - gb_proceeds)
    flows.append(cf)
    inflows.append(gb_proceeds)
    outflows.append(capex)

    outstanding = gb_proceeds  # bullet principal stays constant until maturity
    cumulative_inflation = 1.0

    for t in range(1, project_lifetime + 1):
        idx = t - 1
        cumulative_inflation *= (1 + inflation_rate[idx] / 100.0)
        om_t = annual_maintenace_cost * cumulative_inflation
        om_green_t = OM_green * cumulative_inflation  # O&M for green bond
        revenue = annual_energy_savings * electricity_prices[idx]
        op_cf = revenue - (om_t + om_green_t)

        # Bullet debt service
        if t < term_years:
            interest = outstanding * fixed_interest 
            D_t = interest
        elif t == term_years:
            interest = outstanding * fixed_interest 
            D_t = interest + outstanding
            outstanding = 0.0
        else:
            D_t = 0.0

        inflows.append(revenue)
        outflows.append(om_t + om_green_t + D_t)
        flows.append(op_cf - D_t)

    return flows, inflows, outflows

def cash_flows_epc_guaranteed_savings(
    capex: float,
    annual_energy_savings: float,
    annual_maintenace_cost: float,
    project_lifetime: int,
    electricity_prices: list[float],
    inflation_rate: list[float],
    loan_interest_rate: list[float],
    term_years: int,
    gs: float,
) -> list[float]:
    """Compute yearly net cash-flows for an **EPC guaranteed-savings** contract.

    Parameters
    ----------
    capex : float
        Up-front capital expenditure financed through debt.
    annual_energy_savings : float
        Nominal number of kWh saved per year.
    annual_maintenace_cost : float
        Nominal yearly O&M cost in today's money.
    project_lifetime : int
        Evaluation horizon in *years*.
    electricity_prices : list[float]
        Forecast grid prices for each year.
    inflation_rate : list[float]
        Inflation rates for each year.
    loan_interest_rate : list[float]
        Annual interest rate applicable per remaining principal.
    term_years : int
        Repayment tenor in *years*.
    gs : float
        Guaranteed yearly savings in monetary terms 

    Returns
    -------
    list[float]
        Cash-flow sequence where the first entry is ``0`` because the client
        makes no initial outlay.
    """
    flows = []
    inflows = []
    outflows = []
    flows.append(0)
    inflows.append(capex)
    outflows.append(capex)
    outstanding = capex
    principal = capex / term_years if term_years > 0 else 0
    cumulative_inflation = 1.0

    for t in range(1, project_lifetime + 1):
        idx = t - 1
        cumulative_inflation *= (1 + inflation_rate[idx] / 100.0)
        om_t = annual_maintenace_cost * cumulative_inflation
        gs_t = gs * cumulative_inflation
        # Operating cash flow
        AS_t = annual_energy_savings * electricity_prices[idx]
        op_cf = AS_t - om_t
        # Loan payment
        if t <= term_years:
            interest = outstanding * (loan_interest_rate[idx] / 100.0)
            D_t = principal + interest
            outstanding -= principal
        else:
            D_t = 0.0
        # ESCO compensation
        if AS_t < gs_t:
            comp = gs_t - AS_t
        else:
            comp = 0.0
        cf_t = op_cf - D_t + comp
        inflows.append(AS_t + comp)
        outflows.append(om_t + D_t)
        flows.append(cf_t)

    return flows, inflows, outflows

# we alo need the number of years that the contract is active for and ESCO gets money
def cash_flows_epc_shared_savings(
    annual_energy_savings: float,
    annual_maintenace_cost: float,
    project_lifetime: int,
    electricity_prices: list[float],
    inflation_rate: list[float],
    p_ESCO: float,          # % of savings paid to ESCO (e.g., 0.30 for 30%)
    term_years: int,            # number of years contract is active
) -> list[float]:
    """Compute yearly net cash-flows for an **EPC shared-savings** contract.

    Parameters
    ----------
    annual_energy_savings : float
        Nominal number of kWh saved per year.
    annual_maintenace_cost : float
        Nominal yearly O&M cost in today's money.
    project_lifetime : int
        Evaluation horizon in *years*.
    electricity_prices : list[float]
        Forecast grid prices for each year.
    inflation_rate : list[float]
        Inflation rates for each year.
    p_ESCO : float
        Share of realised savings paid to the ESCO as a fraction.
    term_years : int
        Contract duration in *years* during which the ESCO receives its share.

    Returns
    -------
    list[float]
        Cash-flow sequence where the first entry is ``0`` because the ESCO
        covers the initial CAPEX.
    """
    flows = []
    inflows = []
    outflows = []
    flows.append(0)     # Year 0: ESCO covers entire CAPEX
    inflows.append(0)
    outflows.append(0)
    cumulative_inflation = 1.0

    for t in range(1, project_lifetime + 1):
        idx = t - 1
        cumulative_inflation *= (1 + inflation_rate[idx] / 100.0)
        om_t = annual_maintenace_cost * cumulative_inflation
        AS_t = annual_energy_savings * electricity_prices[idx]
        op_cf = AS_t - om_t
        # ESCO performance charge
        if t <= term_years:
            D_t = AS_t * p_ESCO 
        else:
            D_t = 0.0

        inflows.append(AS_t)
        outflows.append(om_t + D_t)
        flows.append(op_cf - D_t)  

    return flows, inflows, outflows

# makes sense as an ESCO (always good for client? what if maintance is higher that savings?):
def cash_flows_first_out_contract(
    capex: float,
    annual_energy_savings: float,
    annual_maintenace_cost: float,
    project_lifetime: int,
    electricity_prices: list[float],
    inflation_rate: list[float],
) -> tuple[list[float], list[float], list[float]]:
    """Compute yearly net cash-flows for a **first-out ESCO contract**.

    Parameters
    ----------
    capex : float
        Up-front capital expenditure initially covered by the ESCO.
    annual_energy_savings : float
        Nominal number of kWh saved per year.
    annual_maintenace_cost : float
        Nominal yearly O&M cost in today's money.
    project_lifetime : int
        Evaluation horizon in *years*.
    electricity_prices : list[float]
        Forecast grid prices for each year.
    inflation_rate : list[float]
        Inflation rates for each year.

    Returns
    -------
    list[float]
        Cash-flow sequence where the first entry is ``0`` because the client
        makes no initial outlay and savings first repay the ESCO investment.
    """
    flows = []
    inflows = []
    outflows = []
    flows.append(0)  # Year 0: ESCO covers 100% of CAPEX, client pays nothing upfront
    inflows.append(0)
    outflows.append(0)
    D_paid = 0.0
    cumulative_inflation = 1.0

    for t in range(1, project_lifetime + 1):
        idx = t - 1
        cumulative_inflation *= (1 + inflation_rate[idx] / 100.0)
        om_t = annual_maintenace_cost * cumulative_inflation
        AS_t = annual_energy_savings * electricity_prices[idx]
        op_cf = AS_t - om_t

        remaining = capex - D_paid

        if remaining <= 0:
            D_t = 0.0
        else:
            payment_available = max(0.0, op_cf)         
            D_t = min(payment_available, remaining)  
            D_paid += D_t

        cf_t = op_cf - D_t
        inflows.append(AS_t)
        outflows.append(om_t + D_t)
        flows.append(cf_t)

    return flows, inflows, outflows

def cash_flows_royalty_crowdfunding(
    capex: float,
    annual_energy_savings: float,
    annual_maintenace_cost: float,
    project_lifetime: int,
    electricity_prices: list[float],
    inflation_rate: list[float],
    loan_crowd: float,          # capital raised from crowd at t=0
    royalty_rate: float,        # % of gross revenue paid to crowd as royalty (e.g., 0.10 for 10%)
    term_years: int,                # number of years royalty is paid (must be <= project_lifetime)
    fee_plat: float,            # platform success fee rate (e.g., 0.05 for 5%)
) -> list[float]:
    """Compute yearly net cash-flows for **royalty-based crowdfunding**.

    Parameters
    ----------
    capex : float
        Up-front capital expenditure.
    annual_energy_savings : float
        Nominal number of kWh saved per year.
    annual_maintenace_cost : float
        Nominal yearly O&M cost in today's money.
    project_lifetime : int
        Evaluation horizon in *years*.
    electricity_prices : list[float]
        Forecast grid prices for each year.
    inflation_rate : list[float]
        Inflation rates for each year.
    loan_crowd : float
        Capital raised from the crowd at *t = 0*.
    royalty_rate : float
        Percentage of gross revenue paid to the crowd.
    term_years : int
        Number of years during which royalties are paid.
    fee_plat : float
        Platform success fee rate expressed as a fraction.

    Returns
    -------
    list[float]
        Cash-flow sequence where the first entry reflects crowdfunding proceeds,
        platform fees and CAPEX.
    """
    flows = []
    inflows = []
    outflows = []

    # Year 0
    plat_cost = loan_crowd * fee_plat 
    flows.append(loan_crowd - plat_cost - capex)
    inflows.append(loan_crowd)
    outflows.append(plat_cost + capex)
    cumulative_inflation = 1.0

    for t in range(1, project_lifetime + 1):
        idx = t - 1
        cumulative_inflation *= (1 + inflation_rate[idx] / 100.0)
        # Gross revenue (actual savings)
        revenue = annual_energy_savings * electricity_prices[idx]

        # Royalty payment to crowd (off the top)
        if t <= term_years:
            pay_crowd = revenue * (royalty_rate / 100.0)
        else:
            pay_crowd = 0.0

        om_t = annual_maintenace_cost * cumulative_inflation
        inflows.append(revenue)
        outflows.append(pay_crowd + om_t)
        flows.append(revenue - pay_crowd - om_t)

    return flows, inflows, outflows

# the interest rate is usually fixed and agreed beforehand
# acts like a loan through crowdfunding
def cash_flows_lending_crowdfunding(
    capex: float,
    annual_energy_savings: float,
    annual_maintenace_cost: float,
    project_lifetime: int,
    electricity_prices: list[float],
    inflation_rate: list[float],
    loan_crowd: float,      # capital raised from crowd at t=0
    fixed_interest: float,  # fixed predefined interest rate (e.g., 0.05 for 5%)
    term_years: int,         # term of loan in *years* (must be at least 1)
    fee_plat: float,        # platform success fee rate (e.g., 0.05 for 5%)
) -> tuple[list[float], list[float], list[float]]:
    """Compute yearly net cash-flows for **lending-based crowdfunding**.

    Parameters
    ----------
    capex : float
        Up-front capital expenditure.
    annual_energy_savings : float
        Nominal number of kWh saved per year.
    annual_maintenace_cost : float
        Nominal yearly O&M cost in today's money.
    project_lifetime : int
        Evaluation horizon in *years*.
    electricity_prices : list[float]
        Forecast grid prices for each year.
    inflation_rate : list[float]
        Inflation rates for each year.
    loan_crowd : float
        Capital raised from the crowd at *t = 0*.
    fixed_interest : float
        Fixed annual interest rate expressed as a fraction.
    term_years : int
        Repayment tenor in *years*.
    fee_plat : float
        Platform success fee rate expressed as a fraction.

    Returns
    -------
    list[float]
        Cash-flow sequence where the first entry reflects crowdfunding proceeds,
        platform fees and CAPEX.
    """
    flows = []
    inflows = []
    outflows = []

    # Year 0
    plat_cost = loan_crowd * fee_plat 
    flows.append(loan_crowd - plat_cost - capex)
    inflows.append(loan_crowd)
    outflows.append(plat_cost + capex)

    # Fixed annual debt payment 
    r = fixed_interest
    if term_years > 0:
        if r == 0:
            debt_payment = loan_crowd / term_years
        else:
            debt_payment = loan_crowd * (r * (1 + r) ** term_years) / ((1 + r) ** term_years - 1)
    else:
        debt_payment = 0.0

    cumulative_inflation = 1.0
    for t in range(1, project_lifetime + 1):
        idx = t - 1
        cumulative_inflation *= (1 + inflation_rate[idx] / 100.0)
        om_t = annual_maintenace_cost * cumulative_inflation
        AS_t = annual_energy_savings * electricity_prices[idx]
        op_cf = AS_t - om_t

        # Debt service to crowd
        if t <= term_years:
            D_crowd = debt_payment
        else:
            D_crowd = 0.0
        inflows.append(AS_t)
        outflows.append(om_t + D_crowd)
        flows.append(op_cf - D_crowd)
    
    return flows, inflows, outflows

# her investors have co-ownership of the project
def cash_flows_equity_crowdfunding(
    capex: float,
    annual_energy_savings: float,
    annual_maintenace_cost: float,
    project_lifetime: int,
    electricity_prices: list[float],
    inflation_rate: list[float],
    equity_crowd: float,                # capital raised from crowd at t=0
    share_crowd: float,                 # % of profits paid to crowd when positive (e.g., 0.5 for 50%)
    fee_plat: float,                    # platform success fee rate (e.g., 0.05 for 5%)
) -> tuple[list[float], list[float], list[float]]:
    """Compute yearly net cash-flows for **equity crowdfunding**.

    Parameters
    ----------
    capex : float
        Up-front capital expenditure.
    annual_energy_savings : float
        Nominal number of kWh saved per year.
    annual_maintenace_cost : float
        Nominal yearly O&M cost in today's money.
    project_lifetime : int
        Evaluation horizon in *years*.
    electricity_prices : list[float]
        Forecast grid prices for each year.
    inflation_rate : list[float]
        Inflation rates for each year.
    equity_crowd : float
        Equity capital raised from the crowd at *t = 0*.
    share_crowd : float
        Fraction of positive distributable cash-flow allocated to the crowd.
    fee_plat : float
        Platform success fee rate expressed as a fraction.

    Returns
    -------
    list[float]
        Cash-flow sequence where the first entry reflects crowdfunding proceeds,
        platform fees and CAPEX.
    """

    try:
        T = project_lifetime
        flows = []
        inflows = []
        outflows = []
        # Year 0
        plat_cost = equity_crowd * fee_plat
        cf0 = equity_crowd - plat_cost - capex
        flows.append(cf0)
        inflows.append(equity_crowd)
        outflows.append(plat_cost + capex)
        # Operating years
        cumulative_infl = 1.0
        for t in range(1, T + 1):
            idx = t - 1

            cumulative_infl *= (1.0 + inflation_rate[idx] / 100.0)
            revenue = annual_energy_savings * electricity_prices[idx]
            costs = annual_maintenace_cost * cumulative_infl
            distributable_cf = revenue - costs
            # Crowd dividend only if positive CF
            if distributable_cf > 0:
                esco_cf = distributable_cf * (1 - share_crowd)
            else:
                esco_cf = 0.0
            inflows.append(revenue)
            outflows.append(costs + (distributable_cf - esco_cf))
            flows.append(esco_cf)

        return flows, inflows, outflows
    except Exception as exc:
        raise SimulationComputationError(f"Cash-flow computation failed: {exc}") from exc

def cash_flows_with_loan(
    capex: float,
    annual_energy_savings: float,
    annual_maintenace_cost: float,
    project_lifetime: int,
    electricity_prices: list[float],
    inflation_rate: list[float],
    loan_amount: float,
    loan_interest_rate: list[float],
    term_years: int,
) -> tuple[list[float], list[float], list[float]]:
    """Compute the yearly net cash-flow profile **including** debt service.

    Parameters
    ----------
    capex : float
        Up-front capital expenditure (positive number). The function treats this as
        an *outflow* at *t = 0*.
    annual_energy_savings : float
        Nominal number of kWh saved per year.
    annual_maintenace_cost : float
        Nominal yearly O&M cost in today's money.
    project_lifetime : int
        Evaluation horizon in *years* (must be at least 1).
    electricity_prices : list[float]
        Forecast grid prices for each year **indexed the same as `inflation_rate`**.
    inflation_rate : list[float]
        Inflation rates for each year (indexed the same as `electricity_prices`).
    loan_amount : float
        Principal borrowed at *t = 0*.
    loan_interest_rate : list[float]
        Annual interest rate applicable **per remaining principal**.
    term_years : int
        Term of loan in *years* (must be at least 1).
    Returns
    -------
    list[float]
        Sequence of net cash-flows (index 0 … ``project_lifetime``).  The first
        element is *negative* (the equity outflow) and subsequent entries may be
        positive or negative depending on operating surplus and debt service.
    """
    try:
        flows = []
        inflows = []
        outflows = []
        
        # capex minus the loan received
        flows.append(-(capex-loan_amount))
        inflows.append(loan_amount)
        outflows.append(capex)
        
        outstanding = loan_amount
        constant_principal_payment = loan_amount / term_years if term_years > 0 else 0.0
        cumulative_infl = 1.0

        for year in range(0, project_lifetime):
            cumulative_infl *= (1 + inflation_rate[year]/100.0)
            operating_cf = annual_energy_savings * electricity_prices[year] - annual_maintenace_cost * cumulative_infl
            loan_payment = 0.0
            
            if year < term_years and loan_amount > 0:
                interest_payment = outstanding * (loan_interest_rate[year] / 100.0)
                loan_payment = constant_principal_payment + interest_payment
                outstanding -= constant_principal_payment  
            
            inflows.append(annual_energy_savings * electricity_prices[year])
            outflows.append(annual_maintenace_cost * cumulative_infl + loan_payment)
            flows.append(operating_cf - loan_payment)
        
        return flows, inflows, outflows
    except Exception as exc:
        raise SimulationComputationError(f"Cash-flow computation failed: {exc}") from exc

def cash_flows(
    capex: float,
    annual_energy_savings: float,
    annual_maintenace_cost: float,
    project_lifetime: int,
    electricity_prices: list[float],
    inflation_rate: list[float],
) -> tuple[list[float], list[float], list[float]]:
    """Compute yearly net cash-flows for an **equity-only** project.

    This variant omits any debt-service considerations and is therefore a
    simplified special-case of :func:`cash_flows_with_loan`.

    Parameters
    ----------
    capex, annual_energy_savings, annual_maintenace_cost, project_lifetime,
    electricity_prices, inflation_rate : see :func:`cash_flows_with_loan`.

    Returns
    -------
    list[float]
        Cash-flow sequence (first entry negative).
    """
    try:
        flows = [-capex] # t = 0 equity investment
        inflows = [0]
        outflows = [capex]
        cumulative_infl = 1.0
        for k in range(0, project_lifetime):
            cumulative_infl *= (1 + inflation_rate[k]/100.0)
            flow_k = annual_energy_savings * electricity_prices[k] - annual_maintenace_cost * cumulative_infl
            inflows.append(annual_energy_savings * electricity_prices[k])
            outflows.append(annual_maintenace_cost * cumulative_infl)
            flows.append(flow_k)
        return flows, inflows, outflows
    except Exception as exc:
        raise SimulationComputationError(f"Cash-flow computation failed: {exc}") from exc




SCHEME_HANDLERS: dict[str, tuple[Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]], Callable[..., tuple[list[float], list[float], list[float]]]]] = {}


def _scheme_builder(scheme_type: str, details: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    """Build the base inputs expected by each cash-flow function from plain dictionaries."""
    if scheme_type == "equity":
        return {
            "capex": ctx["capex"],
            "annual_energy_savings": ctx["annual_energy_savings"],
            "annual_maintenace_cost": ctx["annual_maintenace_cost"],
            "project_lifetime": ctx["project_lifetime"],
            "electricity_prices": None,
            "inflation_rate": None,
        }

    if scheme_type == "bank_loan":
        return {
            "capex": ctx["capex"],
            "annual_energy_savings": ctx["annual_energy_savings"],
            "annual_maintenace_cost": ctx["annual_maintenace_cost"],
            "project_lifetime": ctx["project_lifetime"],
            "electricity_prices": None,
            "inflation_rate": None,
            "loan_amount": float(details["loan_amount"]),
            "loan_interest_rate": None,
            "term_years": int(details["term_years"]),
        }

    if scheme_type == "operational_lease":
        return {
            "annual_energy_savings": ctx["annual_energy_savings"],
            "project_lifetime": ctx["project_lifetime"],
            "electricity_prices": None,
            "lease_payment": float(details["lease_payment"]),
            "term_years": int(details["term_years"]),
        }

    if scheme_type == "on_bill":
        return {
            "capex": ctx["capex"],
            "annual_energy_savings": ctx["annual_energy_savings"],
            "annual_maintenace_cost": ctx["annual_maintenace_cost"],
            "project_lifetime": ctx["project_lifetime"],
            "electricity_prices": None,
            "inflation_rate": None,
            "term_years": int(details["term_years"]),
            "fixed_interest": float(details["fixed_interest"]),
        }

    if scheme_type == "green_bond_loan":
        return {
            "capex": ctx["capex"],
            "annual_energy_savings": ctx["annual_energy_savings"],
            "annual_maintenace_cost": ctx["annual_maintenace_cost"],
            "project_lifetime": ctx["project_lifetime"],
            "electricity_prices": None,
            "inflation_rate": None,
            "gb_proceeds": float(details["gb_proceeds"]),
            "term_years": int(details["term_years"]),
            "fixed_interest": float(details["fixed_interest"]),
            "OM_green": float(details["OM_green"]),
        }

    if scheme_type == "green_bond_bullet":
        return {
            "capex": ctx["capex"],
            "annual_energy_savings": ctx["annual_energy_savings"],
            "annual_maintenace_cost": ctx["annual_maintenace_cost"],
            "project_lifetime": ctx["project_lifetime"],
            "electricity_prices": None,
            "inflation_rate": None,
            "gb_proceeds": float(details["gb_proceeds"]),
            "term_years": int(details["term_years"]),
            "fixed_interest": float(details["fixed_interest"]),
            "OM_green": float(details["OM_green"]),
        }

    if scheme_type == "epc_guaranteed_savings":
        return {
            "capex": ctx["capex"],
            "annual_energy_savings": ctx["annual_energy_savings"],
            "annual_maintenace_cost": ctx["annual_maintenace_cost"],
            "project_lifetime": ctx["project_lifetime"],
            "electricity_prices": None,
            "inflation_rate": None,
            "loan_interest_rate": None,
            "term_years": int(details["term_years"]),
            "gs": float(details["gs"]),
        }

    if scheme_type == "epc_shared_savings":
        return {
            "annual_energy_savings": ctx["annual_energy_savings"],
            "annual_maintenace_cost": ctx["annual_maintenace_cost"],
            "project_lifetime": ctx["project_lifetime"],
            "electricity_prices": None,
            "inflation_rate": None,
            "p_ESCO": float(details["p_ESCO"]),
            "term_years": int(details["term_years"]),
        }

    if scheme_type == "epc_first_out":
        return {
            "capex": ctx["capex"],
            "annual_energy_savings": ctx["annual_energy_savings"],
            "annual_maintenace_cost": ctx["annual_maintenace_cost"],
            "project_lifetime": ctx["project_lifetime"],
            "electricity_prices": None,
            "inflation_rate": None,
        }

    if scheme_type == "royalty_crowdfunding":
        return {
            "capex": ctx["capex"],
            "annual_energy_savings": ctx["annual_energy_savings"],
            "annual_maintenace_cost": ctx["annual_maintenace_cost"],
            "project_lifetime": ctx["project_lifetime"],
            "electricity_prices": None,
            "inflation_rate": None,
            "loan_crowd": float(details["loan_crowd"]),
            "royalty_rate": float(details["royalty_rate"]),
            "term_years": int(details["term_years"]),
            "fee_plat": float(details["fee_plat"]),
        }

    if scheme_type == "lending_crowdfunding":
        return {
            "capex": ctx["capex"],
            "annual_energy_savings": ctx["annual_energy_savings"],
            "annual_maintenace_cost": ctx["annual_maintenace_cost"],
            "project_lifetime": ctx["project_lifetime"],
            "electricity_prices": None,
            "inflation_rate": None,
            "loan_crowd": float(details["loan_crowd"]),
            "fixed_interest": float(details["fixed_interest"]),
            "term_years": int(details["term_years"]),
            "fee_plat": float(details["fee_plat"]),
        }

    if scheme_type == "equity_crowdfunding":
        return {
            "capex": ctx["capex"],
            "annual_energy_savings": ctx["annual_energy_savings"],
            "annual_maintenace_cost": ctx["annual_maintenace_cost"],
            "project_lifetime": ctx["project_lifetime"],
            # Your Django builder used ctx["capex"] as the amount raised.
            # Change this line if you want to pass a separate equity_crowd input.
            "equity_crowd": float(details.get("equity_crowd", ctx["capex"])),
            "share_crowd": float(details["share_crowd"]),
            "fee_plat": float(details["fee_plat"]),
            "electricity_prices": None,
            "inflation_rate": None,
        }

    raise SchemeConfigurationError(f"Unsupported scheme type: {scheme_type}")


CASHFLOW_FUNCTIONS: dict[str, Callable[..., tuple[list[float], list[float], list[float]]]] = {
    "equity": cash_flows,
    "bank_loan": cash_flows_with_loan,
    "operational_lease": cash_flows_operational_leasing,
    "on_bill": cash_flows_on_bill_financing,
    "green_bond_loan": cash_flows_green_bond_loan,
    "green_bond_bullet": cash_flows_green_bond_bullet,
    "epc_guaranteed_savings": cash_flows_epc_guaranteed_savings,
    "epc_shared_savings": cash_flows_epc_shared_savings,
    "epc_first_out": cash_flows_first_out_contract,
    "royalty_crowdfunding": cash_flows_royalty_crowdfunding,
    "lending_crowdfunding": cash_flows_lending_crowdfunding,
    "equity_crowdfunding": cash_flows_equity_crowdfunding,
}


def create_scheme_definitions(
    *,
    capex: float,
    annual_energy_savings: float,
    annual_maintenace_cost: float,
    project_lifetime: int,
    schemes: list[tuple[str, dict[str, Any]]],
) -> list[dict[str, Any]]:
    """Create scheme definitions from plain Python input."""
    ctx = {
        "capex": float(capex),
        "annual_energy_savings": float(annual_energy_savings),
        "annual_maintenace_cost": float(annual_maintenace_cost),
        "project_lifetime": int(project_lifetime),
    }

    definitions: list[dict[str, Any]] = []
    for idx, (scheme_type, details) in enumerate(schemes, start=1):
        if scheme_type not in CASHFLOW_FUNCTIONS:
            raise SchemeConfigurationError(f"Unsupported scheme type: {scheme_type}")
        definitions.append(
            {
                "scheme_id": idx,
                "scheme_type": scheme_type,
                "cashflow_function": CASHFLOW_FUNCTIONS[scheme_type],
                "base_inputs": _scheme_builder(scheme_type, details, ctx),
            }
        )
    return definitions

def prepare_cashflow_inputs(
    base_inputs: dict[str, Any],
    electricity_prices: list[float],
    inflation_rate: list[float],
    loan_interest_rate: list[float] | None = None,
    annual_energy_savings: float | None = None,
) -> dict[str, Any]:
    """Inject Monte Carlo sampled market inputs into a scheme's base inputs."""
    _ensure(isinstance(base_inputs, dict), f"base_inputs must be a dictionary. Got: {type(base_inputs).__name__}")
    lifetime = _validate_non_negative_integer("project_lifetime", base_inputs.get("project_lifetime"), allow_zero=False)
    _validate_series("electricity_prices", electricity_prices, lifetime)
    _validate_series("inflation_rate", inflation_rate, lifetime)
    if loan_interest_rate is not None:
        _validate_series("loan_interest_rate", loan_interest_rate, lifetime)
    if annual_energy_savings is not None:
        _validate_finite_number("annual_energy_savings", annual_energy_savings)

    inputs = dict(base_inputs)

    if "annual_energy_savings" in inputs and annual_energy_savings is not None:
        inputs["annual_energy_savings"] = float(annual_energy_savings)

    if "electricity_prices" in inputs:
        inputs["electricity_prices"] = electricity_prices

    if "inflation_rate" in inputs:
        inputs["inflation_rate"] = inflation_rate

    if "loan_interest_rate" in inputs:
        inputs["loan_interest_rate"] = (
            loan_interest_rate if loan_interest_rate is not None else [0.0] * lifetime
        )

    return inputs

def IRR(flows: list[float]) -> float:
    """Internal Rate of Return (IRR)."""
    _validate_flows(flows)
    try:
        return npf.irr(flows)
    except Exception as exc:
        raise SimulationComputationError(f"Failed to compute IRR: {exc}") from exc

def NPV(d_r: float, flows: list[float]) -> float:
    """Net Present Value given a constant discount rate."""
    _validate_finite_number("discount rate", d_r)
    _validate_flows(flows)
    try:
        return npf.npv(d_r, flows)
    except Exception as exc:
        raise SimulationComputationError(f"Failed to compute NPV: {exc}") from exc

def PBP(flows: list[float], loan: bool = False, loan_term: int = 0) -> float:
    """Simple (undiscounted) PayBack Period."""
    _validate_flows(flows)
    if loan:
        _validate_non_negative_integer("loan_term", loan_term, allow_zero=True)

    try:
        investment = float(flows[0]) * -1
        if investment <= 0:
            return np.nan

        max_years = 100  # safety limit

        total = 0.0
        previous_total = 0.0
        years = 0

        for i in range(1, max_years + 1):
            if i < len(flows):
                fl = float(flows[i])
            else:
                fl = float(flows[-1])  # option 1: repeat last known cashflow

            previous_total = total
            total += fl
            years += 1

            if total >= investment:
                break
        else:
            return np.nan

        remaining = investment - previous_total
        current_year_contribution = total - previous_total

        if current_year_contribution == 0:
            pbp = float(years)
        else:
            pbp = float(years - 1) + (
                float(remaining) / float(current_year_contribution)
            )

        if loan and not np.isnan(pbp) and pbp < loan_term:
            pbp = loan_term

        return pbp
    except FinancialSimulationError:
        raise
    except Exception as exc:
        raise SimulationComputationError(f"Failed to compute PBP: {exc}") from exc

def DPP(
    d_r: float,
    n: int,
    flows: list[float],
    loan: bool = False,
    loan_term: int = 0,
    max_years: int = 100,
) -> float:
    """Discounted PayBack Period."""
    _validate_finite_number("discount rate", d_r)
    n = _validate_non_negative_integer("n", n, allow_zero=False)
    _validate_flows(flows)
    _ensure(len(flows) >= n + 1, f"flows must contain at least {n + 1} values for DPP calculation. Got: {len(flows)}", SimulationComputationError)
    try:
        discounted_flows = [flows[0]]

        for i in range(1, max_years + 1):
            if i < len(flows):
                cashflow = flows[i]
            else:
                cashflow = flows[-1]  # repeat last known cashflow

            flow_k = cashflow * np.power(1 + float(d_r), -i)
            discounted_flows.append(flow_k)

            if sum(discounted_flows) >= 0:
                break

        dpp = PBP(discounted_flows)

        if loan and not np.isnan(dpp) and dpp < loan_term:
            dpp = loan_term

        return dpp
    except FinancialSimulationError:
        raise
    except Exception as exc:
        raise SimulationComputationError(f"Failed to compute DPP: {exc}") from exc

def ROI(flows: list[float]) -> float:
    """Return on Investment (simple fraction)."""
    _validate_flows(flows)
    initial_investment = -float(flows[0])
    net_profit = sum(float(v) for v in flows[1:])
    if initial_investment == 0:
        return np.nan
    return (net_profit - initial_investment) / initial_investment

# ────────────────────────────────────────────────────────────────────────────────
# Create distribution helpers (80% confidence intervals)
# ────────────────────────────────────────────────────────────────────────────────

Z90 = 1.2815515655446004  # Φ^{-1}(0.90)


def pad_to_length(lst, length):
        """Extend the list to the desired length by repeating the last value."""
        return lst + [lst[-1]] * (length - len(lst)) if len(lst) < length else lst[:length]

def _mu_sigma_from_p10_p50_p90(p10, p50, p90):
    """Assume Normal on the linear scale; return arrays (mu, sigma)."""
    p10 = np.asarray(p10, dtype=float)
    p50 = np.asarray(p50, dtype=float)
    p90 = np.asarray(p90, dtype=float)
    mu = p50
    sigma = (p90 - p10) / (2.0 * Z90)
    # guard against zero/negative spreads
    sigma = np.maximum(sigma, 1e-12)
    return mu, sigma

def _log_mu_sigma_from_p10_p50_p90_prices(p10, p50, p90):
    """
    Electricity prices: use Lognormal ⇒ Normal in log-space.
    optimistic ≈ P90, moderate ≈ P50 (median), pessimistic ≈ P10.
    Returns (mu_ln, sigma_ln).
    """
    eps = 1e-9
    p10 = np.maximum(np.asarray(p10, dtype=float), eps)
    p50 = np.maximum(np.asarray(p50, dtype=float), eps)
    p90 = np.maximum(np.asarray(p90, dtype=float), eps)
    mu_ln = np.log(p50)                      
    sigma_ln = (np.log(p90) - np.log(p10)) / (2.0 * Z90)
    sigma_ln = np.maximum(sigma_ln, 1e-12)
    return mu_ln, sigma_ln


def build_energy_savings_factor_distribution(
    downside_at_p10: float = 0.30,
) -> dict[str, float]:
    """
    Model energy-savings uncertainty as a multiplicative Normal factor.
    Assumption: the 10th percentile is `downside_at_p10` below the base savings.
    Example: downside_at_p10=0.30 => factor P10 = 0.70 and factor P50 = 1.00.
    """
    _ensure(0.0 <= downside_at_p10 < 1.0, "downside_at_p10 must be in [0, 1).", FinancialInputError)

    p10 = 1.0 - downside_at_p10
    p50 = 1.0
    sigma = max((p50 - p10) / Z90, 1e-12)
    return {
        "mu": p50,
        "sigma": sigma,
        "p10": p10,
        "p50": p50,
        "p90": p50 + (p50 - p10),
        "dist": "normal",
        "unit": "factor",
    }


def build_market_distributions(
    inflation_rate_data: dict,
    electricity_prices_data: dict,
    interest_rate_data: dict,
    discount_rate_data: dict,
    project_lifetime: int,
):
    """
    Derive per-year distribution parameters from the 3 scenario paths provided.
    - Inflation, loan interest, discount: Normal(μ, σ) on linear scale.
    - Electricity price: Lognormal via (μ_ln, σ_ln) for stability (keeps > 0).
    Returns a dict with arrays of length == project_lifetime.
    """
    T = min(project_lifetime, 30)

    # pad to project lifetime
    P10_infl = pad_to_length(inflation_rate_data["pessimistic"], T)
    P50_infl = pad_to_length(inflation_rate_data["moderate"], T)
    P90_infl = pad_to_length(inflation_rate_data["optimistic"], T)
    infl_mu, infl_sigma = _mu_sigma_from_p10_p50_p90(P10_infl, P50_infl, P90_infl)

    P10_rate = pad_to_length(interest_rate_data["pessimistic"], T)
    P50_rate = pad_to_length(interest_rate_data["moderate"], T)
    P90_rate = pad_to_length(interest_rate_data["optimistic"], T)
    rate_mu, rate_sigma = _mu_sigma_from_p10_p50_p90(P10_rate, P50_rate, P90_rate)

    # expand discount rate to T
    P10_disc = np.full(T, discount_rate_data["pessimistic"][0], dtype=float)
    P50_disc = np.full(T, discount_rate_data["moderate"][0], dtype=float)
    P90_disc = np.full(T, discount_rate_data["optimistic"][0], dtype=float)
    disc_mu, disc_sigma = _mu_sigma_from_p10_p50_p90(P10_disc, P50_disc, P90_disc)

    P10_elec = pad_to_length(electricity_prices_data["pessimistic"], T)
    P50_elec = pad_to_length(electricity_prices_data["moderate"], T)
    P90_elec = pad_to_length(electricity_prices_data["optimistic"], T)
    elec_mu_ln, elec_sigma_ln = _log_mu_sigma_from_p10_p50_p90_prices(P10_elec, P50_elec, P90_elec)

    return {
        'inflation':  {'mu': infl_mu,  'sigma': infl_sigma,               'dist': 'normal',   'unit': '% y/y'},
        'loan_rate':  {'mu': rate_mu,  'sigma': rate_sigma,               'dist': 'normal',   'unit': '% y/y'},
        'discount':   {'mu': disc_mu,  'sigma': disc_sigma,               'dist': 'normal',   'unit': 'fraction'},
        'elec_price': {'mu_ln': elec_mu_ln, 'sigma_ln': elec_sigma_ln,    'dist': 'lognormal','unit': '€/kWh'},
        'T': T
    }

# ────────────────────────────────────────────────────────────────────────────────
# Scenario analysis function
# ────────────────────────────────────────────────────────────────────────────────

def get_kpi_results(
    *,
    capex: float,
    annual_energy_savings: float,
    annual_maintenace_cost: float,
    project_lifetime: int,
    schemes: list[tuple[str, dict[str, Any]]],
    n_sims: int = 10000,
    seed: int = 42,
) -> dict[str, Any]:
    """Run Monte Carlo KPI simulations for all configured schemes."""
    scheme_definitions = create_scheme_definitions(
        capex=capex,
        annual_energy_savings=annual_energy_savings,
        annual_maintenace_cost=annual_maintenace_cost,
        project_lifetime=project_lifetime,
        schemes=schemes,
    )
    if not scheme_definitions:
        raise ExperimentConfigurationError("Experiment does not contain any runnable scheme definitions.")

    project_lifetime = int(scheme_definitions[0]["base_inputs"]["project_lifetime"])

    if n_sims <= 0:
        raise FinancialInputError(f"n_sims must be positive, got: {n_sims}")
    if n_sims > 1000000:
        raise FinancialInputError(f"n_sims is too large (max 1,000,000), got: {n_sims}")
    if not isinstance(seed, int):
        raise FinancialInputError(f"seed must be an integer, got: {type(seed).__name__}")
    if project_lifetime <= 0:
        raise FinancialInputError(f"project_lifetime must be positive, got: {project_lifetime}")
    if project_lifetime > 30: # TODO fix this
        project_lifetime = 30

    inflation_rate_data = {
        'optimistic': pad_to_length([7.515, 9.293, 9.162, 9.021, 10.11, 10.46, 10.29, 10.90, 11.41, 11.40, 11.73, 12.23, 12.38, 12.59, 13.00, 13.25, 13.44, 13.77, 14.05, 14.26, 14.53, 14.82, 15.05, 15.30, 15.57, 15.82, 16.05, 16.32, 16.56, 16.80], project_lifetime),
        'moderate': pad_to_length([6.11, 7.40, 6.96, 6.45, 7.20, 7.30, 6.87, 7.19, 7.48, 7.24, 7.33, 7.60, 7.54, 7.54, 7.74, 7.79, 7.77, 7.90, 7.99, 8.01, 8.09, 8.19, 8.23, 8.29, 8.39, 8.45, 8.50, 8.58, 8.65, 8.71], project_lifetime),
        'pessimistic': pad_to_length([4.70, 5.51, 4.77, 3.88, 4.29, 4.14, 3.44, 3.49, 3.54, 3.08, 2.92, 2.98, 2.71, 2.49, 2.48, 2.32, 2.11, 2.04, 1.94, 1.76, 1.65, 1.56, 1.41, 1.29, 1.20, 1.08, 0.95, 0.85, 0.74, 0.62], project_lifetime)
    }

    electricity_prices_data = {
        'optimistic': pad_to_length([0.271, 0.279, 0.287, 0.295, 0.303, 0.311, 0.319, 0.327, 0.335, 0.343, 0.351, 0.360, 0.368, 0.376, 0.384, 0.392, 0.400, 0.408], project_lifetime),
        'moderate': pad_to_length([0.246, 0.254, 0.262, 0.270, 0.278, 0.286, 0.294, 0.302, 0.310, 0.318, 0.326, 0.335, 0.343, 0.351, 0.359, 0.367, 0.375, 0.383], project_lifetime),
        'pessimistic': pad_to_length([0.221, 0.229, 0.237, 0.245, 0.253, 0.261, 0.269, 0.277, 0.285, 0.293, 0.301, 0.310, 0.318, 0.326, 0.334, 0.342, 0.350, 0.358], project_lifetime)
    }

    interest_rate_data = {
        'optimistic': pad_to_length([5.075, 3.750, 2.425, 1.312, 1.312, 1.312, 1.312, 1.312, 1.312, 1.312, 1.312, 1.312, 1.312, 1.312, 1.312, 1.00], project_lifetime),
        'moderate': pad_to_length([3.272, 1.947, 0.622, -0.49, -0.49, -0.49, -0.49, -0.49, -0.49, -0.49, -0.49, -0.49, -0.49, -0.49, -0.49, -0.49], project_lifetime),
        'pessimistic': pad_to_length([1.470, 0.145, -1.17, -2.29, -2.29, -2.29, -2.29, -2.29, -2.29, -2.29, -2.29, -2.29, -2.29, -2.29, -2.29, -2.29], project_lifetime)
    }

    discount_rate_data = {
        "optimistic": [0.02],
        "moderate": [0.06],
        "pessimistic": [0.08],
    }

    try:
        dist_params = build_market_distributions(
            inflation_rate_data=inflation_rate_data,
            electricity_prices_data=electricity_prices_data,
            interest_rate_data=interest_rate_data,
            discount_rate_data=discount_rate_data,
            project_lifetime=project_lifetime,
        )
    except Exception as exc:
        raise SimulationComputationError(f"Failed to build market distributions: {exc}") from exc

    rng = np.random.default_rng(seed)
    T = project_lifetime

    infl = rng.normal(dist_params['inflation']['mu'], dist_params['inflation']['sigma'], size=(n_sims, T))
    rate = rng.normal(dist_params['loan_rate']['mu'], dist_params['loan_rate']['sigma'], size=(n_sims, T))
    disc = rng.normal(dist_params['discount']['mu'], dist_params['discount']['sigma'], size=(n_sims, T))
    elec = np.exp(rng.normal(dist_params['elec_price']['mu_ln'], dist_params['elec_price']['sigma_ln'], size=(n_sims, T)))
    energy_savings_factor_dist = build_energy_savings_factor_distribution()
    energy_savings_factor = rng.normal(
        energy_savings_factor_dist["mu"],
        energy_savings_factor_dist["sigma"],
        size=n_sims,
    )

    infl = np.maximum(infl, -50.0)
    rate = np.maximum(rate, -50.0)
    disc = np.maximum(disc, -0.99)
    elec = np.maximum(elec, 1e-9)
    energy_savings_factor = np.maximum(energy_savings_factor, 0.0)
    dist_params["energy_savings"] = energy_savings_factor_dist

    results: dict[str, Any] = {}

    for scheme_def in scheme_definitions:
        print("Running simulations for scheme:", scheme_def["scheme_type"])
        scheme_type = scheme_def["scheme_type"]
        cashflow_function = scheme_def["cashflow_function"]
        base_inputs = scheme_def["base_inputs"]

        irr = np.full(n_sims, np.nan)
        npv = np.full(n_sims, np.nan)
        pbp = np.full(n_sims, np.nan)
        dpp = np.full(n_sims, np.nan)
        roi = np.full(n_sims, np.nan)
        total_repayment = np.full(n_sims, np.nan)
        cashflow_paths = np.full((n_sims, T + 1), np.nan)
        inflow_paths = np.full((n_sims, T + 1), np.nan)
        outflow_paths = np.full((n_sims, T + 1), np.nan)

        for i in range(n_sims):
            elec_i = elec[i, :].tolist()
            infl_i = infl[i, :].tolist()
            rate_i = rate[i, :].tolist()
            disc_i = float(disc[i, 0])
            base_energy_savings = float(base_inputs["annual_energy_savings"])
            energy_savings_i = base_energy_savings * float(energy_savings_factor[i])
            # infl_i = [2 for x in infl_i]
            try:
                inputs = prepare_cashflow_inputs(
                    base_inputs=base_inputs,
                    electricity_prices=elec_i,
                    inflation_rate=infl_i,
                    loan_interest_rate=rate_i,
                    annual_energy_savings=energy_savings_i,
                )
                flows, inflows, outflows = cashflow_function(**inputs)
                _validate_flows(flows)
                _ensure(
                    isinstance(inflows, list) and isinstance(outflows, list),
                    f"Cash-flow function for scheme '{scheme_type}' must return list inflows/outflows.",
                    SimulationComputationError,
                )
                _ensure(
                    len(inflows) == len(flows) == len(outflows),
                    f"Cash-flow, inflow, and outflow lengths must match for scheme '{scheme_type}'.",
                    SimulationComputationError,
                )
                irr[i] = IRR(flows)
                npv[i] = NPV(disc_i, flows)
                # if flows[0] == 0:
                #     pbp[i] = 0
                #     dpp[i] = 0
                if "term_years" in inputs and inputs["term_years"]:
                    pbp[i] = PBP(flows, loan=True, loan_term=int(inputs["term_years"]))
                    dpp[i] = DPP(disc_i, T, flows, loan=True, loan_term=int(inputs["term_years"]))
                else:
                    pbp[i] = PBP(flows)
                    dpp[i] = DPP(disc_i, T, flows)
                roi[i] = ROI(flows)
                total_repayment[i] = float(np.sum(np.asarray(outflows[1:], dtype=float)))
                cashflow_paths[i, :] = np.asarray(flows, dtype=float)
                inflow_paths[i, :] = np.asarray(inflows, dtype=float)
                outflow_paths[i, :] = np.asarray(outflows, dtype=float)
            except FinancialSimulationError:
                raise
            except Exception as exc:
                raise SimulationComputationError(
                    f"Simulation failed for scheme '{scheme_type}' at iteration {i}: {exc}"
                ) from exc

        censor_value = T + 1
        pbp_censored = np.where(~np.isfinite(pbp) | (pbp > T), censor_value, pbp)
        dpp_censored = np.where(~np.isfinite(dpp) | (dpp > T), censor_value, dpp)

        def pct(a, qs=(5, 10, 25, 50, 75, 90, 95)):
            a = np.asarray(a, dtype=float)
            return {f"P{q}": np.nanpercentile(a, q) for q in qs}

        def pct_by_year(paths, qs=(5, 10, 25, 50, 75, 90, 95)):
            arr = np.asarray(paths, dtype=float)
            return {
                f"P{q}": np.nanpercentile(arr, q, axis=0).tolist()
                for q in qs
            }

        disc_target = float(np.nanmedian(disc[:, 0]))

        def pr(mask):
            m = np.asarray(mask, dtype=bool)
            return float(np.nanmean(m))

        summary = {
            "percentiles": {
                "IRR": pct(irr),
                "NPV": pct(npv),
                "PBP": pct(pbp_censored),
                "DPP": pct(dpp_censored),
                "ROI": pct(roi),
                "total_repayment": pct(total_repayment),
            },
            "probabilities": {
                "Pr(NPV > 0)": pr(npv > 0),
                f"Pr(PBP < {T}y)": pr(pbp < T),
                f"Pr(DPP < {T}y)": pr(dpp < T),
            },
            "disc_target_used": disc_target,
            "n_sims": n_sims,
        }

        kpi_histograms = {
            "NPV": _build_kpi_histogram_payload("NPV", npv),
            "IRR": _build_kpi_histogram_payload("IRR", irr),
            "ROI": _build_kpi_histogram_payload("ROI", roi),
            "PBP": _build_kpi_histogram_payload(
                "PBP",
                pbp,
                project_lifetime=T,
            ),
            "DPP": _build_kpi_histogram_payload(
                "DPP",
                dpp,
                project_lifetime=T,
            ),
        }

        results[scheme_type] = {
            "scheme_id": scheme_def["scheme_id"],
            "summary": summary,
            "kpi_histograms": kpi_histograms,
            "cashflow_distributions": {
                "years": list(range(T + 1)),
                "cash_flows": pct_by_year(cashflow_paths),
                "inflows": pct_by_year(inflow_paths),
                "outflows": pct_by_year(outflow_paths),
            },
        }
    return results



def print_summary_table(results: dict[str, Any]) -> None:
    """Print a compact summary for quick local testing."""
    header = f"{'scheme':<26} {'NPV P50':>12} {'IRR P50':>10} {'PBP P50':>10} {'DPP P50':>10} {'Pr NPV>0':>10}"
    print(header)
    print("-" * len(header))
    for scheme_type, result in results.items():
        summary = result["summary"]
        pct = summary["percentiles"]
        probs = summary["probabilities"]
        npv_p50 = pct["NPV"]["P50"]
        irr_p50 = pct["IRR"]["P50"]
        pbp_p50 = pct["PBP"]["P50"]
        dpp_p50 = pct["DPP"]["P50"]
        pr_npv = probs["Pr(NPV > 0)"]
        print(
            f"{scheme_type:<26} "
            f"{npv_p50:>12,.2f} "
            f"{irr_p50:>10.2%} "
            f"{pbp_p50:>10.2f} "
            f"{dpp_p50:>10.2f} "
            f"{pr_npv:>10.1%}"
        )


def main() -> None:
    capex = 1000
    borrowed_amount = 1000
    annual_energy_savings = 400
    annual_maintenace_cost = 100
    project_lifetime = 20
    n_sims = 10000
    seed = 42

    example_schemes = [
        ("equity", {}),
        ("bank_loan", {"loan_amount": borrowed_amount, "term_years": 5}),
        ("operational_lease", {"lease_payment": 200, "term_years": 5}),
        ("on_bill", {"term_years": 5, "fixed_interest": 0.05}),
        ("green_bond_loan", {"gb_proceeds": borrowed_amount, "term_years": 5, "fixed_interest": 0.045, "OM_green": 100}),
        ("green_bond_bullet", {"gb_proceeds": borrowed_amount, "term_years": 5, "fixed_interest": 0.045, "OM_green": 100}),
        ("epc_guaranteed_savings", {"term_years": 5, "gs": 500}),
        ("epc_shared_savings", {"term_years": 5, "p_ESCO": 0.30}),
        ("epc_first_out", {}),
        ("royalty_crowdfunding", {"loan_crowd": borrowed_amount, "royalty_rate": 10.0, "term_years": 5, "fee_plat": 0.05}),
        ("lending_crowdfunding", {"loan_crowd": borrowed_amount, "fixed_interest": 0.06, "term_years": 5, "fee_plat": 0.05}),
        ("equity_crowdfunding", {"share_crowd": 0.40, "fee_plat": 0.05}),
    ]

    results = get_kpi_results(
        capex=capex,
        annual_energy_savings=annual_energy_savings,
        annual_maintenace_cost=annual_maintenace_cost,
        project_lifetime=project_lifetime,
        schemes=example_schemes,
        n_sims=n_sims,
        seed=seed,
    )

    print_summary_table(results)

    output_path = Path("simulation_results.json")
    output_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nFull results written to: {output_path.resolve()}")


if __name__ == "__main__":
    main()

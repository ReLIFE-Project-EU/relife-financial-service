"""
Risk Assessment Service - Business Logic Layer

This module implements the core business logic for financial risk assessment
of energy retrofit projects using Monte Carlo simulation.

Main Functions:
    - perform_risk_assessment: Orchestrates the entire risk assessment workflow
    - _build_private_output: Constructs output for individual homeowners
    - _build_professional_output: Constructs output for energy consultants
    - _build_public_output: Constructs output for public institutions
    - _build_complete_output: Constructs output with visualizations

Dependencies:
    - simulation_engine: Monte Carlo simulation
    - indicator_outputs: KPI formatting utilities
    - visualizations: Chart generation (for complete output)
"""

import sys
from pathlib import Path
from typing import Dict, Any, Optional
import math
import numpy as np
import numpy_financial as npf

# Add Indicator Modules to path
indicator_modules_path = Path(__file__).parent.parent / "Indicator Modules"
if str(indicator_modules_path) not in sys.path:
    sys.path.insert(0, str(indicator_modules_path))

from simulation_engine import run_simulation
from indicator_outputs import get_point_forecast
from visualizations import generate_private_cash_flow_chart

from ..models.risk_assessment import (
    RiskAssessmentRequest,
    RiskAssessmentResponse,
    OutputLevel
)





# ============================================================================
# Main Service Function
# ============================================================================

async def perform_risk_assessment(request: RiskAssessmentRequest) -> RiskAssessmentResponse:
    """
    Perform comprehensive Monte Carlo risk assessment.
    
    Orchestrates the entire risk assessment workflow:
    1. Validates inputs and retrieves missing parameters (capex, OPEX) from dataset if needed
    2. Runs Monte Carlo simulation (10,000 scenarios)
    3. Processes results based on output_level
    4. Returns structured response
    
    Args:
        request: RiskAssessmentRequest containing all input parameters
        
    Returns:
        RiskAssessmentResponse with fields populated based on output_level
        
    Raises:
        ValueError: If invalid parameters or missing required data
        RuntimeError: If simulation fails
    """
    
    # ─────────────────────────────────────────────────────────────
    # Step 1: Parameter Validation & Dataset Lookup
    # ─────────────────────────────────────────────────────────────
    
    # TODO: Implement dataset lookup for capex/OPEX if None
    # For now, require explicit values
    if request.capex is None:
        raise ValueError("capex is required (dataset lookup not yet implemented)")
    if request.annual_maintenance_cost is None:
        raise ValueError("annual_maintenance_cost is required (dataset lookup not yet implemented)")
    
    capex = request.capex
    annual_maintenance_cost = request.annual_maintenance_cost
    
    # Validate loan doesn't exceed capex
    if request.loan_amount > capex:
        raise ValueError(
            f"loan_amount ({request.loan_amount}) cannot exceed capex ({capex})"
        )
    
    # ─────────────────────────────────────────────────────────────
    # Step 2: Run Monte Carlo Simulation
    # ─────────────────────────────────────────────────────────────
    
    try:
        simulation_results = run_simulation(
            capex=capex,
            annual_maintenace_cost=annual_maintenance_cost,
            annual_energy_savings=request.annual_energy_savings,
            project_lifetime=request.project_lifetime,
            loan_amount=request.loan_amount,
            loan_term=request.loan_term,
            loan_rate=None,  # Use market-simulated rates
            n_sims=10000,
            seed=42  # Fixed seed for reproducibility
        )
    except Exception as e:
        raise RuntimeError(f"Simulation failed: {str(e)}")
    
    # ─────────────────────────────────────────────────────────────
    # Step 3: Build Output Based on Level
    # ─────────────────────────────────────────────────────────────
    
    if request.output_level == OutputLevel.private:
        return _build_private_output(request, simulation_results)
    elif request.output_level == OutputLevel.professional:
        return _build_professional_output(request, simulation_results)
    elif request.output_level == OutputLevel.public:
        return _build_public_output(request, simulation_results)
    elif request.output_level == OutputLevel.complete:
        return _build_complete_output(request, simulation_results)
    else:
        raise ValueError(f"Unknown output_level: {request.output_level}")


def _sanitize_for_json(value: Any) -> Any:
    """
    Recursively replace NaN/Inf values with None so FastAPI/Starlette
    can serialize responses without ValueError: out of range float.
    """
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return 0.0
    if isinstance(value, dict):
        return {k: _sanitize_for_json(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [ _sanitize_for_json(v) for v in value ]
    return value


def _finite_or_zero(val: float) -> float:
    """Return val if finite, otherwise 0.0."""
    if isinstance(val, (int, float)) and math.isfinite(val):
        return float(val)
    return 0.0


# ============================================================================
# Private Output (Individual Homeowners)
# ============================================================================

def _build_private_output(
    request: RiskAssessmentRequest,
    results: Dict[str, Any]
) -> RiskAssessmentResponse:
    """
    Build output for private users (individual homeowners).
    
    Focus: Comprehensive risk assessment with percentile distributions
    - Percentile distributions (P10-P90) for core financial indicators
    - Point forecasts for intuitive metrics
    - Cash flow visualization
    
    Included Metrics:
        Distributions (P10, P20, P30, P40, P50, P60, P70, P80, P90):
            - NPV: Total net profit over project lifetime
            - PBP: Simple payback period (years to break even)
            - ROI: Total return on investment as percentage
            - IRR: Internal rate of return
            - DPP: Discounted payback period
        
        Point Forecasts:
            - Monthly Savings: Average monthly financial benefit
            - Success Rate: Probability of positive return
    
    Args:
        request: Original request parameters
        results: Raw simulation results from run_simulation()
        
    Returns:
        RiskAssessmentResponse with percentile distributions in point_forecasts and metadata
    """
    import numpy as np
    
    raw_data = results['raw_data']
    
    # ─────────────────────────────────────────────────────────────
    # Calculate Percentile Distributions for Core Financial Metrics
    # ─────────────────────────────────────────────────────────────
    
    kpi_distributions = {}
    point_forecasts = {}
    
    # Define percentiles to calculate
    percentiles = [10, 20, 30, 40, 50, 60, 70, 80, 90]
    
    # Core Financial Metrics - Return full distributions AND point forecast (P50)
    if "NPV" in request.indicators:
        npv_percentiles = np.nanpercentile(raw_data['npv'], percentiles)
        kpi_distributions["NPV"] = {
            f"P{p}": _finite_or_zero(npv_percentiles[i]) 
            for i, p in enumerate(percentiles)
        }
        point_forecasts["NPV"] = _finite_or_zero(npv_percentiles[4])  # P50 is at index 4
    
    if "PBP" in request.indicators:
        pbp_percentiles = np.nanpercentile(raw_data['pbp'], percentiles)
        kpi_distributions["PBP"] = {
            f"P{p}": _finite_or_zero(pbp_percentiles[i]) 
            for i, p in enumerate(percentiles)
        }
        point_forecasts["PBP"] = _finite_or_zero(pbp_percentiles[4])
    
    if "ROI" in request.indicators:
        roi_percentiles = np.nanpercentile(raw_data['roi'], percentiles)
        kpi_distributions["ROI"] = {
            f"P{p}": _finite_or_zero(roi_percentiles[i]) 
            for i, p in enumerate(percentiles)
        }
        point_forecasts["ROI"] = _finite_or_zero(roi_percentiles[4])
    
    if "IRR" in request.indicators:
        irr_percentiles = np.nanpercentile(raw_data['irr'], percentiles)
        kpi_distributions["IRR"] = {
            f"P{p}": _finite_or_zero(irr_percentiles[i]) 
            for i, p in enumerate(percentiles)
        }
        point_forecasts["IRR"] = _finite_or_zero(irr_percentiles[4])
    
    if "DPP" in request.indicators:
        dpp_percentiles = np.nanpercentile(raw_data['dpp'], percentiles)
        kpi_distributions["DPP"] = {
            f"P{p}": _finite_or_zero(dpp_percentiles[i]) 
            for i, p in enumerate(percentiles)
        }
        point_forecasts["DPP"] = _finite_or_zero(dpp_percentiles[4])
    
    # Additional Intuitive Metrics for Homeowners
    # Average Monthly Savings: (Total savings over lifetime) / (lifetime in months)
    total_savings_over_lifetime = np.nanmedian(raw_data['npv']) + (
        request.capex if request.capex else 0
    ) - request.loan_amount
    monthly_savings = total_savings_over_lifetime / (request.project_lifetime * 12)
    point_forecasts["MonthlyAvgSavings"] = round(_finite_or_zero(monthly_savings), 2)
    
    # Success Rate: Probability of positive NPV
    success_rate = float(np.mean(raw_data['npv'] > 0))
    point_forecasts["SuccessRate"] = round(_finite_or_zero(success_rate), 3)
    
    # ─────────────────────────────────────────────────────────────
    # Build Metadata
    # ─────────────────────────────────────────────────────────────
    
    metadata = {
        "n_sims": 10000,
        "project_lifetime": request.project_lifetime,
        "capex": request.capex,
        "annual_maintenance_cost": request.annual_maintenance_cost,
        "annual_energy_savings": request.annual_energy_savings,
        "loan_amount": request.loan_amount,
        "loan_term": request.loan_term,
        "output_level": request.output_level.value,
        "indicators_requested": request.indicators,
    }
    
    # Add loan payment info if applicable
    if request.loan_amount > 0 and request.loan_term > 0:
        # Calculate annual payment from metadata if available
        loan_rate = results.get('metadata', {}).get('loan_rate')
        
        # If no fixed loan rate, use median of sampled interest rates
        if loan_rate is None:
            dist_params = results.get('market_distributions', {})
            loan_rate_mu = dist_params.get('loan_rate', {}).get('mu')
            if loan_rate_mu is not None:
                loan_rate = float(loan_rate_mu[0]) / 100  # Convert percentage to decimal (3.5 -> 0.035)
            else:
                loan_rate = 0.04  # Fallback to 4%
        
        if loan_rate and loan_rate > 0:
            annual_payment = float(npf.pmt(loan_rate, request.loan_term, -request.loan_amount))
            metadata["annual_loan_payment"] = round(annual_payment, 2)
            metadata["loan_rate_percent"] = round(loan_rate * 100, 2)  # Store as percentage for readability (3.5%)
    
    # ─────────────────────────────────────────────────────────────
    # Generate Cash Flow Data for Frontend Visualization
    # ─────────────────────────────────────────────────────────────
    
    # Calculate cash flow data that frontend will use to render the chart
    market_dist = results['market_distributions']
    
    # Calculate median values from market distributions
    median_elec_prices = np.exp(market_dist['elec_price']['mu_ln'])
    median_inflation = market_dist['inflation']['mu']
    
    # Annual revenues from energy savings
    annual_revenues = request.annual_energy_savings * median_elec_prices[:request.project_lifetime]
    
    # Annual maintenance costs (inflated over time)
    annual_opex = np.array([
        request.annual_maintenance_cost * np.prod([1 + median_inflation[j]/100 for j in range(i+1)]) 
        for i in range(request.project_lifetime)
    ])
    
    # Calculate loan payments if applicable
    if request.loan_amount > 0 and request.loan_term > 0:
        loan_rate = results.get('metadata', {}).get('loan_rate')
        if loan_rate is None:
            loan_rate_mu = market_dist.get('loan_rate', {}).get('mu')
            if loan_rate_mu is not None:
                loan_rate = float(loan_rate_mu[0]) / 100
            else:
                loan_rate = 0.04
        
        annual_loan_payment = float(npf.pmt(loan_rate, request.loan_term, -request.loan_amount))
        annual_loan_payments = np.zeros(request.project_lifetime)
        annual_loan_payments[:request.loan_term] = annual_loan_payment
    else:
        annual_loan_payments = np.zeros(request.project_lifetime)
    
    # Total outflows and net cash flow
    total_annual_outflows = annual_opex + annual_loan_payments
    annual_net_cf = annual_revenues - total_annual_outflows
    
    # Cumulative position for break-even calculation
    cumulative_position = np.zeros(request.project_lifetime + 1)
    cumulative_position[0] = -(request.capex - request.loan_amount)
    for i in range(request.project_lifetime):
        cumulative_position[i+1] = cumulative_position[i] + annual_net_cf[i]
    
    # Find break-even year
    breakeven_year = int(np.where(cumulative_position >= 0)[0][0]) if any(cumulative_position >= 0) else None
    
    # Prepare cash flow data for frontend
    cash_flow_data = {
        "years": list(range(0, request.project_lifetime + 1)),
        "initial_investment": float(request.capex - request.loan_amount),
        "annual_inflows": [0.0] + [float(x) for x in annual_revenues],  # Year 0 has no inflows
        "annual_outflows": [float(request.capex - request.loan_amount)] + [float(x) for x in total_annual_outflows],
        "annual_net_cash_flow": [float(cumulative_position[0])] + [float(x) for x in annual_net_cf],  # Year 0 is negative (outflow)
        "cumulative_cash_flow": [float(x) for x in cumulative_position],
        "breakeven_year": breakeven_year,
        "loan_term": request.loan_term if request.loan_amount > 0 else None
    }
    
    # Add cash flow data to metadata for frontend rendering
    metadata["cash_flow_data"] = cash_flow_data
    
    # ─────────────────────────────────────────────────────────────
    # Return Response
    # ─────────────────────────────────────────────────────────────
    
    return RiskAssessmentResponse(
        point_forecasts=_sanitize_for_json(point_forecasts),
        percentiles=_sanitize_for_json(kpi_distributions),
        metadata=_sanitize_for_json(metadata)
    )


# ============================================================================
# Professional Output 
# ============================================================================

def _build_professional_output(
    request: RiskAssessmentRequest,
    results: Dict[str, Any]
) -> RiskAssessmentResponse:
    """
    Build output for professional users (energy consultants, advisors).
    
    Focus: Detailed analysis for technical professionals
    - Point forecasts (P50 median values)
    - Full percentile distributions (P10-P90) for all indicators
    - Success probability metrics
    - Chart metadata for distribution graphs
    
    Includes:
        - Percentiles for IRR, NPV, PBP, DPP, ROI
        - Probabilities: NPV > 0, PBP < lifetime, DPP < lifetime
        - Metadata for generating 5 distribution charts client-side
    
    Args:
        request: Original request parameters
        results: Raw simulation results from run_simulation()
        
    Returns:
        RiskAssessmentResponse with point_forecasts, percentiles, probabilities, metadata
    """
    
    raw_data = results['raw_data']
    
    # ─────────────────────────────────────────────────────────────
    # Build Point Forecasts (P50 Median)
    # ─────────────────────────────────────────────────────────────
    
    point_forecasts = {}
    
    if "NPV" in request.indicators:
        point_forecasts["NPV"] = float(np.median(raw_data['npv']))
    
    if "IRR" in request.indicators:
        point_forecasts["IRR"] = float(np.median(raw_data['irr']))
    
    if "ROI" in request.indicators:
        point_forecasts["ROI"] = float(np.median(raw_data['roi']))
    
    if "PBP" in request.indicators:
        point_forecasts["PBP"] = float(np.median(raw_data['pbp']))
    
    if "DPP" in request.indicators:
        point_forecasts["DPP"] = float(np.median(raw_data['dpp']))
    
    # ─────────────────────────────────────────────────────────────
    # Build Full Percentile Distributions
    # ─────────────────────────────────────────────────────────────
    
    # Percentiles for professional analysis: P10, P20, ..., P90
    percentiles = [10, 20, 30, 40, 50, 60, 70, 80, 90]
    indicator_percentiles = {}
    
    if "NPV" in request.indicators:
        npv_vals = np.percentile(raw_data['npv'], percentiles)
        indicator_percentiles["NPV"] = {
            f"P{p}": float(npv_vals[i]) 
            for i, p in enumerate(percentiles)
        }
    
    if "IRR" in request.indicators:
        irr_vals = np.percentile(raw_data['irr'], percentiles)
        indicator_percentiles["IRR"] = {
            f"P{p}": float(irr_vals[i]) 
            for i, p in enumerate(percentiles)
        }
    
    if "ROI" in request.indicators:
        roi_vals = np.percentile(raw_data['roi'], percentiles)
        indicator_percentiles["ROI"] = {
            f"P{p}": float(roi_vals[i]) 
            for i, p in enumerate(percentiles)
        }
    
    if "PBP" in request.indicators:
        pbp_vals = np.percentile(raw_data['pbp'], percentiles)
        indicator_percentiles["PBP"] = {
            f"P{p}": float(pbp_vals[i]) 
            for i, p in enumerate(percentiles)
        }
    
    if "DPP" in request.indicators:
        dpp_vals = np.percentile(raw_data['dpp'], percentiles)
        indicator_percentiles["DPP"] = {
            f"P{p}": float(dpp_vals[i]) 
            for i, p in enumerate(percentiles)
        }
    
    # ─────────────────────────────────────────────────────────────
    # Calculate Success Probabilities
    # ─────────────────────────────────────────────────────────────
    
    probabilities = {}
    
    # Probability of positive NPV
    if "NPV" in request.indicators:
        prob_npv_positive = float(np.mean(raw_data['npv'] > 0))
        probabilities["Pr(NPV > 0)"] = round(prob_npv_positive, 4)
    
    # Probability that simple payback occurs within project lifetime
    if "PBP" in request.indicators:
        prob_pbp_within_lifetime = float(
            np.mean(raw_data['pbp'] < request.project_lifetime)
        )
        probabilities[f"Pr(PBP < {request.project_lifetime}y)"] = round(
            prob_pbp_within_lifetime, 4
        )
    
    # Probability that discounted payback occurs within project lifetime
    if "DPP" in request.indicators:
        prob_dpp_within_lifetime = float(
            np.mean(raw_data['dpp'] < request.project_lifetime)
        )
        probabilities[f"Pr(DPP < {request.project_lifetime}y)"] = round(
            prob_dpp_within_lifetime, 4
        )
    
    # ─────────────────────────────────────────────────────────────
    # Build Chart Metadata for Frontend Visualization
    # ─────────────────────────────────────────────────────────────
    
    # For each indicator, provide histogram bins for client-side rendering
    chart_metadata = {}
    
    for indicator in request.indicators:
        indicator_key = indicator.upper()
        data_array = raw_data[indicator.lower()]
        
        # Calculate histogram bins (30 bins for smooth distribution)
        hist, bin_edges = np.histogram(data_array, bins=30, density=False)
        bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2
        
        # Get P10/P50/P90 for vertical lines on chart
        p10, p50, p90 = np.percentile(data_array, [10, 50, 90])
        
        # Calculate statistics
        mean_val = float(np.mean(data_array))
        std_val = float(np.std(data_array))
        
        chart_metadata[indicator_key] = {
            "bins": {
                "centers": [float(x) for x in bin_centers],
                "counts": [int(x) for x in hist],
                "edges": [float(x) for x in bin_edges]
            },
            "statistics": {
                "mean": round(mean_val, 4),
                "std": round(std_val, 4),
                "P10": round(float(p10), 4),
                "P50": round(float(p50), 4),
                "P90": round(float(p90), 4)
            },
            "chart_config": {
                "xlabel": _get_indicator_label(indicator_key),
                "ylabel": "Frequency (Number of Scenarios)",
                "title": f"{indicator_key} Distribution ({results['metadata']['n_sims']:,} Simulations)"
            }
        }
    
    # ─────────────────────────────────────────────────────────────
    # Build Metadata
    # ─────────────────────────────────────────────────────────────
    
    metadata = {
        "n_sims": results['metadata']['n_sims'],
        "project_lifetime": request.project_lifetime,
        "capex": request.capex,
        "annual_maintenance_cost": request.annual_maintenance_cost,
        "annual_energy_savings": request.annual_energy_savings,
        "loan_amount": request.loan_amount,
        "loan_term": request.loan_term,
        "output_level": request.output_level.value,
        "indicators_requested": request.indicators,
        "chart_metadata": chart_metadata  # Metadata for generating distribution charts
    }
    
    # Add discount rate used in simulation
    disc_rate = results.get('metadata', {}).get('disc_target', 0.06)
    metadata["discount_rate"] = round(float(disc_rate), 4)
    
    # ─────────────────────────────────────────────────────────────
    # Return Response
    # ─────────────────────────────────────────────────────────────
    
    return RiskAssessmentResponse(
        point_forecasts=point_forecasts,
        percentiles=indicator_percentiles,
        probabilities=probabilities,
        metadata=metadata
    )


def _get_indicator_label(indicator: str) -> str:
    """Get human-readable label for indicator."""
    labels = {
        "NPV": "Net Present Value (€)",
        "IRR": "Internal Rate of Return (%)",
        "ROI": "Return on Investment (%)",
        "PBP": "Payback Period (years)",
        "DPP": "Discounted Payback Period (years)"
    }
    return labels.get(indicator, indicator)


# ============================================================================
# Public Output (Public Institutions)
# ============================================================================

def _build_public_output(
    request: RiskAssessmentRequest,
    results: Dict[str, Any]
) -> RiskAssessmentResponse:
    """
    Build output for public users (government, research institutions).
    
    Focus: Comprehensive statistical analysis
    - Point forecasts
    - Key percentiles (P10/P50/P90)
    - Full percentile breakdown (P5/P10/P25/P50/P75/P90/P95)
    - Success probabilities
    - Detailed metadata
    
    TODO: Implement public-level output
    
    Args:
        request: Original request parameters
        results: Raw simulation results from run_simulation()
        
    Returns:
        RiskAssessmentResponse with all statistical fields populated
    """
    # TODO: Implement
    raise NotImplementedError("Public output not yet implemented")


# ============================================================================
# Complete Output (With Visualizations)
# ============================================================================

def _build_complete_output(
    request: RiskAssessmentRequest,
    results: Dict[str, Any]
) -> RiskAssessmentResponse:
    """
    Build complete output with visualizations.
    
    Focus: Everything including charts
    - All statistical data from public output
    - Base64-encoded visualization images
    - Cash flow breakdown chart
    - Indicator distribution charts
    
    TODO: Implement complete output with visualizations
    
    Args:
        request: Original request parameters
        results: Raw simulation results from run_simulation()
        
    Returns:
        RiskAssessmentResponse with visualizations included
    """
    # TODO: Implement
    raise NotImplementedError("Complete output with visualizations not yet implemented")

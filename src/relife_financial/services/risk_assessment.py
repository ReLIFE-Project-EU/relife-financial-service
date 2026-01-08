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
import numpy as np
import numpy_financial as npf

# Add Indicator Modules to path
indicator_modules_path = Path(__file__).parent.parent.parent.parent / "Indicator Modules"
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


# ============================================================================
# Private Output (Individual Homeowners)
# ============================================================================

def _build_private_output(
    request: RiskAssessmentRequest,
    results: Dict[str, Any]
) -> RiskAssessmentResponse:
    """
    Build output for private users (individual homeowners).
    
    Focus: Maximum simplicity and intuitiveness
    - Only median (P50) values
    - Only the most essential metrics homeowners care about
    - No percentile distributions or complex statistics
    
    Included Metrics:
        - NPV: Total net profit over project lifetime
        - PBP: Simple payback period (years to break even)
        - ROI: Total return on investment as percentage
        - Monthly Savings: Average monthly financial benefit
        - Success Rate: Probability of positive return
    
    Args:
        request: Original request parameters
        results: Raw simulation results from run_simulation()
        
    Returns:
        RiskAssessmentResponse with only point_forecasts and metadata
    """
    import numpy as np
    
    raw_data = results['raw_data']
    
    # ─────────────────────────────────────────────────────────────
    # Calculate Point Forecasts (Median Values)
    # ─────────────────────────────────────────────────────────────
    
    point_forecasts = {}
    
    # Core Financial Metrics
    if "NPV" in request.indicators:
        point_forecasts["NPV"] = float(np.median(raw_data['npv']))
    
    if "PBP" in request.indicators:
        point_forecasts["PBP"] = float(np.median(raw_data['pbp']))
    
    if "ROI" in request.indicators:
        point_forecasts["ROI"] = float(np.median(raw_data['roi']))
    
    if "IRR" in request.indicators:
        point_forecasts["IRR"] = float(np.median(raw_data['irr']))
    
    if "DPP" in request.indicators:
        point_forecasts["DPP"] = float(np.median(raw_data['dpp']))
    
    # Additional Intuitive Metrics for Homeowners
    # Average Monthly Savings: (Total savings over lifetime) / (lifetime in months)
    total_savings_over_lifetime = np.median(raw_data['npv']) + (
        request.capex if request.capex else 0
    ) - request.loan_amount
    monthly_savings = total_savings_over_lifetime / (request.project_lifetime * 12)
    point_forecasts["MonthlyAvgSavings"] = round(float(monthly_savings), 2)
    
    # Success Rate: Probability of positive NPV
    success_rate = float(np.mean(raw_data['npv'] > 0))
    point_forecasts["SuccessRate"] = round(success_rate, 3)
    
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
    # Generate Cash Flow Visualization (Private users get 1 key chart)
    # ─────────────────────────────────────────────────────────────
    
    cash_flow_chart = generate_private_cash_flow_chart(
        capex=request.capex,
        project_lifetime=request.project_lifetime,
        annual_energy_savings=request.annual_energy_savings,
        annual_maintenance_cost=request.annual_maintenance_cost,
        loan_amount=request.loan_amount,
        loan_term=request.loan_term,
        market_distributions=results['market_distributions'],
        loan_rate=results.get('metadata', {}).get('loan_rate'),
        return_base64=True
    )
    
    visualizations = {
        "cash_flow_timeline": cash_flow_chart
    }
    
    # ─────────────────────────────────────────────────────────────
    # Return Response
    # ─────────────────────────────────────────────────────────────
    
    return RiskAssessmentResponse(
        point_forecasts=point_forecasts,
        metadata=metadata,
        key_percentiles=None,
        probabilities=None,
        percentiles=None,
        visualizations=visualizations
    )


# ============================================================================
# Professional Output (Energy Consultants)
# ============================================================================

def _build_professional_output(
    request: RiskAssessmentRequest,
    results: Dict[str, Any]
) -> RiskAssessmentResponse:
    """
    Build output for professional users (energy consultants, advisors).
    
    Focus: Balanced detail for technical professionals
    - Point forecasts (P50)
    - Key percentiles (P10/P50/P90) for risk assessment
    - Success probabilities
    - No full percentile breakdown (that's for public)
    
    TODO: Implement professional-level output
    
    Args:
        request: Original request parameters
        results: Raw simulation results from run_simulation()
        
    Returns:
        RiskAssessmentResponse with point_forecasts, key_percentiles, probabilities, metadata
    """
    # TODO: Implement
    raise NotImplementedError("Professional output not yet implemented")


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

"""
Risk Assessment API Routes

This module defines the HTTP endpoints for Monte Carlo risk assessment
of energy retrofit projects.

Endpoints:
    POST /risk-assessment - Run comprehensive Monte Carlo simulation
"""

from typing import Optional

from fastapi import APIRouter, HTTPException, status

from relife_financial.auth.dependencies import OptionalAuthenticatedUserDep
from relife_financial.config.logging import get_logger
from relife_financial.config.settings import SettingsDep
from relife_financial.models.risk_assessment import (
    RiskAssessmentRequest,
    RiskAssessmentResponse,
)
from relife_financial.services.risk_assessment import perform_risk_assessment

router = APIRouter(tags=["risk-assessment"], prefix="/risk-assessment")

logger = get_logger(__name__)


@router.post("", response_model=RiskAssessmentResponse, status_code=status.HTTP_200_OK)
async def assess_project_risk(
    request: RiskAssessmentRequest,
    current_user: OptionalAuthenticatedUserDep,
    settings: SettingsDep,
) -> RiskAssessmentResponse:
    """
    Perform comprehensive Monte Carlo risk assessment for energy retrofit project.
    
    This endpoint runs a Monte Carlo simulation (10,000 scenarios) to assess the financial
    risk and returns of an energy retrofit investment. The response complexity depends on
    the requested output_level:
    
    - **private**: For individual homeowners - only median values and key metrics
    - **professional**: For energy consultants - includes percentiles and probabilities
    - **public**: For institutions - full statistical breakdown
    - **complete**: Everything including visualizations
    
    **Authentication**: Optional. If a valid JWT token is provided, user information
    will be logged for audit purposes.
    
    Parameters
    ----------
    request : RiskAssessmentRequest
        Project parameters including:
        - capex: Total investment cost (€)
        - annual_energy_savings: Annual energy savings estimate (kWh/year)
        - annual_maintenance_cost: Yearly O&M cost (€)
        - project_lifetime: Project duration (years, max 30)
        - schemes: List of financing schemes to evaluate (discriminated by scheme_type)
        - output_level: Response complexity (private/professional/public/complete)
        - indicators: List of KPIs to calculate (NPV, IRR, ROI, PBP, DPP)
    
    Returns
    -------
    RiskAssessmentResponse
        Financial risk assessment results with fields populated based on output_level:
        - point_forecasts: Median values (all levels)
        - metadata: Simulation parameters (all levels)
        - percentiles: P10-P90 distributions (professional), P5-P95 (public+)
        - probabilities: Success rates (professional+)
        - visualizations: Charts as base64 (complete only, private gets cash flow)
    
    Raises
    ------
    HTTPException 400
        - Invalid input parameters (e.g., loan > capex)
        - Missing required parameters
    HTTPException 500
        - Simulation execution failed
        - Unexpected processing error
    
    Example Request
    ---------------
    ```json
    {
        "capex": 60000,
        "annual_energy_savings": 27400,
        "annual_maintenance_cost": 2000,
        "project_lifetime": 20,
        "output_level": "professional",
        "schemes": [
            {"scheme_type": "equity"},
            {"scheme_type": "bank_loan", "loan_amount": 25000, "term_years": 15},
            {"scheme_type": "epc_shared_savings", "p_ESCO": 0.30, "term_years": 10}
        ],
        "indicators": ["NPV", "IRR", "PBP", "ROI"]
    }
    ```
    
    Example Response (professional level, equity scheme only shown)
    ---------------------------------------------------------------
    ```json
    {
        "results": {
            "equity": {
                "scheme_id": 1,
                "scheme_family": "self_financed",
                "summary": {
                    "percentiles": {"IRR": {"P50": 0.084}, "NPV": {"P50": 15400}},
                    "probabilities": {"Pr(NPV > 0)": 0.952},
                    "disc_target_used": 0.05,
                    "n_sims": 10000
                },
                "kpi_histograms": {"NPV": {...}, "IRR": {...}},
                "cashflow_distributions": {"years": [0, 1, ..., 20], "cash_flows": {...}}
            }
        },
        "metadata": {
            "capex": 60000,
            "project_lifetime": 20,
            "n_schemes": 1,
            "output_level": "professional"
        }
    }
    ```
    
    Notes
    -----
    - Simulation uses 10,000 Monte Carlo scenarios with fixed seed for reproducibility
    - Market parameters (electricity prices, inflation, loan rates) are sampled from distributions
    - Execution time: typically 2-5 seconds depending on project_lifetime
    - Visualizations (when included) are base64-encoded PNGs ready for direct display
    """
    
    user_id = current_user.user_id if current_user else "anonymous"
    
    try:
        logger.info(
            "Risk assessment requested",
            user_id=user_id,
            capex=request.capex,
            project_lifetime=request.project_lifetime,
            output_level=request.output_level.value,
            n_schemes=len(request.schemes),
            scheme_types=[s.scheme_type for s in request.schemes],
            indicators=request.indicators,
        )
        
        # Perform the risk assessment
        response = await perform_risk_assessment(request)
        
        logger.info(
            "Risk assessment completed successfully",
            user_id=user_id,
            output_level=request.output_level.value,
            n_sims=response.metadata.get("n_sims") if response.metadata else None,
        )
        
        return response
        
    except ValueError as e:
        # Invalid input parameters
        logger.warning(
            "Risk assessment validation error",
            user_id=user_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid request parameters: {str(e)}"
        )
    
    except RuntimeError as e:
        # Simulation execution error
        logger.error(
            "Risk assessment simulation failed",
            user_id=user_id,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Simulation failed: {str(e)}"
        )
    
    except Exception as e:
        # Unexpected error
        logger.error(
            "Risk assessment unexpected error",
            user_id=user_id,
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during risk assessment"
        )

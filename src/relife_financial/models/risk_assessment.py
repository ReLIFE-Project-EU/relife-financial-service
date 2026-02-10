"""
Pydantic models for risk assessment endpoint.

This module defines the data contracts (request/response structure) for the
comprehensive Monte Carlo risk assessment API.

Models:
    - OutputLevel: Enum defining available detail levels
    - RiskAssessmentRequest: Input parameters for simulation
    - RiskAssessmentResponse: Output structure with conditional fields
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any
from enum import Enum


class OutputLevel(str, Enum):
    """
    Output detail level for risk assessment response.
    
    Automatically determined by which frontend tool is being used:
    - private: Individual homeowners - basic metrics plus intuitive summaries/graphs (~2 KB)
    - professional: Energy consultants/professionals - detailed analysis (~5 KB)
    - public: Public institutions - comprehensive reports (~10 KB)
    - complete: Special cases requiring charts - includes visualizations (~500 KB - 2 MB)
    
    Note: This is set by the frontend based on the tool context, NOT selected by end-users.
    """
    private = "private"
    professional = "professional"
    public = "public"
    complete = "complete"


class RiskAssessmentRequest(BaseModel):
    """
    Request model for Monte Carlo risk assessment.
    
    Defines all input parameters needed for comprehensive financial risk assessment
    of energy retrofit projects using Monte Carlo simulation.
    
    Attributes:
        Project Parameters:
            capex: Capital expenditure in euros (optional - falls back to dataset if None)
            annual_maintenance_cost: Annual O&M cost in euros (optional - falls back to dataset if None)
            annual_energy_savings: Annual energy saved in kWh (provided by another API)
            project_lifetime: Project horizon in years (1-30, required)
        
        Financing Parameters:
            loan_amount: Loan principal in euros (user input, default: 0 = all-equity)
            loan_term: Loan repayment period in years (user input, default: 0)
        
        Output Control:
            output_level: Detail level determined by frontend tool (private/professional/public/complete)
            indicators: Which KPIs to include (default: all 5)
            include_visualizations: Override to force include/exclude charts (default: None)
    """
    
    # ─────────────────────────────────────────────────────────────
    # Project Parameters
    # ─────────────────────────────────────────────────────────────
    capex: Optional[float] = Field(
        default=None,
        gt=0,
        description=(
            "Capital expenditure (CAPEX) in euros. Must be positive if provided. "
            "If None, value will be retrieved from internal dataset."
        ),
        examples=[60000]
    )
    
    annual_maintenance_cost: Optional[float] = Field(
        default=None,
        ge=0,
        description=(
            "Annual maintenance and operational cost (OPEX) in euros. "
            "If None, value will be retrieved from internal dataset."
        ),
        examples=[2000]
    )
    
    annual_energy_savings: float = Field(
        ...,
        gt=0,
        description="Expected annual energy savings in kWh. Provided by external energy consumption API.",
        examples=[27400]
    )
    
    project_lifetime: int = Field(
        ...,
        ge=1,
        le=30,
        description="Project evaluation horizon in years. Maximum 30 years.",
        examples=[20]
    )
    
    # ─────────────────────────────────────────────────────────────
    # Financing Parameters
    # ─────────────────────────────────────────────────────────────
    loan_amount: float = Field(
        default=0.0,
        ge=0,
        description=(
            "Loan amount in euros (user input). Defaults to 0 for all-equity financing. "
            "If > 0, loan_term must also be provided."
        ),
        examples=[25000]
    )
    
    loan_term: int = Field(
        default=0,
        ge=0,
        description=(
            "Loan repayment term in years (user input). "
            "Must be > 0 if loan_amount > 0."
        ),
        examples=[15]
    )
    
    # ─────────────────────────────────────────────────────────────
    # Output Control
    # ─────────────────────────────────────────────────────────────
    output_level: OutputLevel = Field(
        ...,
        description=(
            "Output detail level. Automatically determined by which frontend tool is used: "
            "private (homeowners), professional (consultants), public (institutions), complete (with charts). "
            "NOT selected by end-users."
        )
    )
    
    indicators: List[str] = Field(
        default=["IRR", "NPV", "PBP", "DPP", "ROI"],
        description="Which financial indicators to include in response.",
        examples=[["IRR", "NPV", "PBP"]]
    )
    
    include_visualizations: Optional[bool] = Field(
        default=None,
        description=(
            "Override output_level to explicitly include/exclude visualizations. "
            "None means follow output_level default (only 'complete' includes viz)."
        )
    )
    
    # ─────────────────────────────────────────────────────────────
    # Validators
    # ─────────────────────────────────────────────────────────────
    @field_validator('loan_amount')
    @classmethod
    def validate_loan_amount(cls, v, info):
        """Ensure loan_amount doesn't exceed capex (if capex is provided)."""
        if 'capex' in info.data and info.data['capex'] is not None:
            if v > info.data['capex']:
                raise ValueError(
                    f"loan_amount ({v}) cannot exceed capex ({info.data['capex']})"
                )
        # Note: If capex is None, this validation will be done in service layer after fetching from dataset
        return v
    
    @field_validator('loan_term')
    @classmethod
    def validate_loan_term(cls, v, info):
        """Ensure loan_term is valid when loan_amount is provided."""
        if 'loan_amount' in info.data:
            loan_amount = info.data['loan_amount']
            if loan_amount > 0 and v == 0:
                raise ValueError("loan_term must be > 0 when loan_amount > 0")
            if 'project_lifetime' in info.data and v > info.data['project_lifetime']:
                raise ValueError(
                    f"loan_term ({v}) cannot exceed project_lifetime ({info.data['project_lifetime']})"
                )
        return v
    
    @field_validator('indicators')
    @classmethod
    def validate_indicators(cls, v):
        """Ensure only valid indicators are requested."""
        valid_indicators = {"IRR", "NPV", "PBP", "DPP", "ROI"}
        invalid = set(v) - valid_indicators
        if invalid:
            raise ValueError(
                f"Invalid indicators: {invalid}. Must be one of: {valid_indicators}"
            )
        if not v:
            raise ValueError("At least one indicator must be specified")
        return v
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "annual_energy_savings": 27400,
                    "project_lifetime": 20,
                    "output_level": "private",
                    "loan_amount": 25000,
                    "loan_term": 15,
                    "indicators": ["IRR", "NPV", "PBP"]
                },
                {
                    "capex": 60000,
                    "annual_maintenance_cost": 2000,
                    "annual_energy_savings": 27400,
                    "project_lifetime": 20,
                    "output_level": "professional",
                    "loan_amount": 0,
                    "loan_term": 0
                }
            ]
        }
    }


class RiskAssessmentResponse(BaseModel):
    """
    Response model for risk assessment endpoint.
    
    Structure varies based on output_level set by frontend tool:
    
    private (homeowners):
        - point_forecasts (P50 values + intuitive metrics)
        - percentiles (P10-P90 distributions for KPIs)
        - metadata (includes cash_flow_data for frontend chart rendering)
    
    professional (consultants):
        - point_forecasts (P50 median values)
        - percentiles (P10-P90 distributions for all 5 indicators)
        - probabilities (NPV > 0, PBP < lifetime, DPP < lifetime)
        - metadata (includes chart_metadata for distribution graphs)
    
    public (institutions):
        - point_forecasts
        - percentiles (full P5-P95 breakdown)
        - probabilities
        - metadata
    
    complete (special cases):
        - All of the above
        - visualizations (base64-encoded images)
    
    Attributes:
        point_forecasts: Median (P50) value for each requested indicator
        metadata: Simulation parameters and settings used
        percentiles: Percentile distributions (P10-P90 for professional, P5-P95 for public)
        probabilities: Success probability metrics (professional+)
        visualizations: Base64-encoded chart images (complete only)
    """
    
    # ─────────────────────────────────────────────────────────────
    # Always Included (All Levels)
    # ─────────────────────────────────────────────────────────────
    point_forecasts: Dict[str, float] = Field(
        ...,
        description="Median (P50) value for each indicator. Always included.",
        examples=[{"IRR": 0.057, "NPV": 5432.1, "PBP": 8.3}]
    )
    
    metadata: Dict[str, Any] = Field(
        ...,
        description="Simulation metadata: n_sims, project_lifetime, loan info, etc.",
        examples=[{
            "n_sims": 10000,
            "project_lifetime": 20,
            "loan_amount": 25000,
            "loan_term": 15,
            "disc_target_used": 0.06
        }]
    )
    
    # ─────────────────────────────────────────────────────────────
    # Professional and Above
    # ─────────────────────────────────────────────────────────────

    probabilities: Optional[Dict[str, float]] = Field(
        default=None,
        description=(
            "Success probability metrics. Included in 'professional' and above. "
            "Keys: 'Pr(NPV > 0)', 'Pr(PBP < Ny)', 'Pr(DPP < Ny)' where N is project lifetime."
        ),
        examples=[{
            "Pr(NPV > 0)": 0.8435,
            "Pr(PBP < 20y)": 0.9124,
            "Pr(DPP < 20y)": 0.7563
        }]
    )
    
    # ─────────────────────────────────────────────────────────────
    # Public and Complete
    # ─────────────────────────────────────────────────────────────
    percentiles: Optional[Dict[str, Dict[str, float]]] = Field(
        default=None,
        description=(
            "Percentile distributions for each indicator. "
            "Professional: P10-P90 (9 percentiles). "
            "Public/Complete: P5-P95 (full breakdown). "
            "Used for distribution analysis and chart rendering."
        ),
        examples=[{
            "IRR": {"P10": 0.031, "P20": 0.040, "P30": 0.046, "P40": 0.052, "P50": 0.057,
                    "P60": 0.063, "P70": 0.070, "P80": 0.079, "P90": 0.089},
            "NPV": {"P10": 2100.0, "P20": 3200.0, "P30": 4100.0, "P40": 4800.0,
                    "P50": 5432.1, "P60": 6100.0, "P70": 6900.0, "P80": 7800.0, "P90": 9800.0}
        }]
    )
    
    # ─────────────────────────────────────────────────────────────
    # Complete Only (or explicit request)
    # ─────────────────────────────────────────────────────────────
    visualizations: Optional[Dict[str, str]] = Field(
        default=None,
        description=(
            "Base64-encoded PNG images of charts. "
            "Keys: '<indicator>_chart' for individual charts, 'dashboard' for comprehensive view. "
            "Only included in 'complete' output_level or when explicitly requested."
        ),
        examples=[{
            "IRR_chart": "data:image/png;base64,iVBORw0KGgo...",
            "dashboard": "data:image/png;base64,iVBORw0KGgo..."
        }]
    )
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "point_forecasts": {
                        "IRR": 0.057,
                        "NPV": 5432.1,
                        "PBP": 8.3,
                        "DPP": 10.1,
                        "ROI": 15.2
                    },
                    "percentiles": {
                        "IRR": {"P10": 0.031, "P20": 0.040, "P30": 0.046, "P40": 0.052, 
                                "P50": 0.057, "P60": 0.063, "P70": 0.070, "P80": 0.079, "P90": 0.089},
                        "NPV": {"P10": 2100.0, "P20": 3200.0, "P30": 4100.0, "P40": 4800.0,
                                "P50": 5432.1, "P60": 6100.0, "P70": 6900.0, "P80": 7800.0, "P90": 9800.0}
                    },
                    "probabilities": {
                        "Pr(NPV > 0)": 0.8435,
                        "Pr(PBP < 20y)": 0.9124,
                        "Pr(DPP < 20y)": 0.7563
                    },
                    "metadata": {
                        "n_sims": 10000,
                        "project_lifetime": 20,
                        "chart_metadata": {
                            "NPV": {
                                "bins": {"centers": [], "counts": [], "edges": []},
                                "statistics": {"mean": 5500.0, "std": 2300.0, "P10": 2100.0, "P50": 5432.1, "P90": 9800.0},
                                "chart_config": {"xlabel": "Net Present Value (€)", "ylabel": "Frequency (Number of Scenarios)", "title": "NPV Distribution (10,000 Simulations)"}
                            }
                        }
                    }
                }
            ]
        }
    }

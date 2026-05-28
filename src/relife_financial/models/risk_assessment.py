"""
Pydantic models for the risk assessment endpoint.

Supports 12 financing schemes across 4 families, selected via a discriminated union.
"""
from __future__ import annotations
from enum import Enum
from typing import Annotated, Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field, field_validator


class OutputLevel(str, Enum):
    """
    Output detail level for risk assessment response.
    - private:       Individual homeowners - summary + cash-flow bands
    - professional:  Energy consultants - adds KPI histograms
    - public:        Institutions - full statistical breakdown
    - complete:      All of the above (reserved for future visualizations)
    """
    private = "private"
    professional = "professional"
    public = "public"
    complete = "complete"


# ─────────────────────────────────────────────────────────────────────────────
# Per-scheme input models (12 schemes across 4 families)
# ─────────────────────────────────────────────────────────────────────────────
# All rate/fraction inputs (fixed_interest, p_ESCO, royalty_rate, fee_plat,
# share_crowd) are expressed as fractions, e.g. 0.05 means 5%.
# ─────────────────────────────────────────────────────────────────────────────

class EquitySchemeInput(BaseModel):
    """Family: self_financed. Client pays full CAPEX upfront."""
    scheme_type: Literal["equity"] = "equity"
    scheme_family: Literal["self_financed"] = "self_financed"


class BankLoanSchemeInput(BaseModel):
    """Family: debt_financed. Standard amortising bank loan."""
    scheme_type: Literal["bank_loan"] = "bank_loan"
    scheme_family: Literal["debt_financed"] = "debt_financed"
    loan_amount: float = Field(..., gt=0, description="Loan principal (EUR)")
    term_years: int = Field(..., ge=1, description="Repayment term (years)")


class GreenBondLoanSchemeInput(BaseModel):
    """Family: debt_financed. Green bond with amortising repayment."""
    scheme_type: Literal["green_bond_loan"] = "green_bond_loan"
    scheme_family: Literal["debt_financed"] = "debt_financed"
    gb_proceeds: float = Field(..., gt=0, description="Bond proceeds (EUR)")
    term_years: int = Field(..., ge=1, description="Bond term (years)")
    fixed_interest: float = Field(..., ge=0.0, le=1.0, description="Fixed annual coupon rate (fraction, e.g. 0.05)")
    OM_green: float = Field(..., ge=0, description="Additional annual O&M for green-bond administration (EUR/year)")


class GreenBondBulletSchemeInput(BaseModel):
    """Family: debt_financed. Green bond with bullet (lump-sum) repayment."""
    scheme_type: Literal["green_bond_bullet"] = "green_bond_bullet"
    scheme_family: Literal["debt_financed"] = "debt_financed"
    gb_proceeds: float = Field(..., gt=0)
    term_years: int = Field(..., ge=1)
    fixed_interest: float = Field(..., ge=0.0, le=1.0, description="Fixed annual coupon rate (fraction)")
    OM_green: float = Field(..., ge=0)


class OnBillSchemeInput(BaseModel):
    """Family: esco_zero_capex. Utility/provider covers CAPEX; client repays via bill."""
    scheme_type: Literal["on_bill"] = "on_bill"
    scheme_family: Literal["esco_zero_capex"] = "esco_zero_capex"
    term_years: int = Field(..., ge=1, description="Repayment term via utility bill (years)")
    fixed_interest: float = Field(..., ge=0.0, le=1.0, description="Annual interest rate (fraction)")


class OperationalLeaseSchemeInput(BaseModel):
    """Family: esco_zero_capex. Lessor owns and maintains equipment; client pays fixed lease."""
    scheme_type: Literal["operational_lease"] = "operational_lease"
    scheme_family: Literal["esco_zero_capex"] = "esco_zero_capex"
    lease_payment: float = Field(..., gt=0, description="Annual lease payment (EUR/year, includes O&M)")
    term_years: int = Field(..., ge=1, description="Lease term (years)")


class EpcSharedSavingsSchemeInput(BaseModel):
    """Family: esco_zero_capex. ESCO covers CAPEX; client shares savings for contract duration."""
    scheme_type: Literal["epc_shared_savings"] = "epc_shared_savings"
    scheme_family: Literal["esco_zero_capex"] = "esco_zero_capex"
    p_ESCO: float = Field(..., ge=0.0, le=1.0, description="ESCO share of realised savings (fraction)")
    term_years: int = Field(..., ge=1, description="Shared-savings contract duration (years)")


class EpcFirstOutSchemeInput(BaseModel):
    """Family: esco_zero_capex. ESCO covers CAPEX; recoups from all net savings until recovered."""
    scheme_type: Literal["epc_first_out"] = "epc_first_out"
    scheme_family: Literal["esco_zero_capex"] = "esco_zero_capex"


class EpcGuaranteedSavingsSchemeInput(BaseModel):
    """Family: esco_zero_capex. Client finances via bank loan; ESCO guarantees minimum savings."""
    scheme_type: Literal["epc_guaranteed_savings"] = "epc_guaranteed_savings"
    scheme_family: Literal["esco_zero_capex"] = "esco_zero_capex"
    term_years: int = Field(..., ge=1, description="Bank loan repayment term (years)")
    gs: float = Field(..., ge=0, description="ESCO-guaranteed annual savings in today's money (EUR/year)")


class LendingCrowdfundingSchemeInput(BaseModel):
    """Family: crowdfunding. Crowd provides fixed-rate debt; repaid as annuity."""
    scheme_type: Literal["lending_crowdfunding"] = "lending_crowdfunding"
    scheme_family: Literal["crowdfunding"] = "crowdfunding"
    loan_crowd: float = Field(..., gt=0, description="Capital raised from crowd (EUR)")
    fixed_interest: float = Field(..., ge=0.0, le=1.0, description="Fixed annual interest rate (fraction)")
    term_years: int = Field(..., ge=1, description="Repayment term (years)")
    fee_plat: float = Field(..., ge=0.0, le=1.0, description="Platform fee as fraction of capital raised")


class RoyaltyCrowdfundingSchemeInput(BaseModel):
    """Family: crowdfunding. Crowd receives a royalty fraction of revenue for contract duration."""
    scheme_type: Literal["royalty_crowdfunding"] = "royalty_crowdfunding"
    scheme_family: Literal["crowdfunding"] = "crowdfunding"
    loan_crowd: float = Field(..., gt=0)
    royalty_rate: float = Field(..., ge=0.0, le=1.0, description="Royalty as fraction of gross revenue (e.g. 0.10)")
    term_years: int = Field(..., ge=1)
    fee_plat: float = Field(..., ge=0.0, le=1.0)


class EquityCrowdfundingSchemeInput(BaseModel):
    """Family: crowdfunding. Crowd receives an ownership share of distributable cash flow."""
    scheme_type: Literal["equity_crowdfunding"] = "equity_crowdfunding"
    scheme_family: Literal["crowdfunding"] = "crowdfunding"
    equity_crowd: float = Field(..., gt=0, description="Equity capital raised from crowd (EUR)")
    share_crowd: float = Field(..., ge=0.0, le=1.0, description="Crowd ownership fraction of distributable CF")
    fee_plat: float = Field(..., ge=0.0, le=1.0)


SchemeInput = Annotated[
    Union[
        EquitySchemeInput,
        BankLoanSchemeInput,
        GreenBondLoanSchemeInput,
        GreenBondBulletSchemeInput,
        OnBillSchemeInput,
        OperationalLeaseSchemeInput,
        EpcSharedSavingsSchemeInput,
        EpcFirstOutSchemeInput,
        EpcGuaranteedSavingsSchemeInput,
        LendingCrowdfundingSchemeInput,
        RoyaltyCrowdfundingSchemeInput,
        EquityCrowdfundingSchemeInput,
    ],
    Field(discriminator="scheme_type"),
]


# ─────────────────────────────────────────────────────────────────────────────
# Request / Response
# ─────────────────────────────────────────────────────────────────────────────

class RiskAssessmentRequest(BaseModel):
    """Request model for multi-scheme Monte Carlo risk assessment."""

    # Project parameters
    capex: float = Field(..., gt=0, description="Total capital expenditure (EUR)", examples=[60000])
    annual_energy_savings: float = Field(
        ..., gt=0,
        description="Base annual energy savings estimate (kWh/year). Treated stochastically (P10 = 0.70x).",
        examples=[27400],
    )
    annual_maintenance_cost: float = Field(
        default=0.0, ge=0,
        description="Annual O&M cost in today's money (EUR/year)",
        examples=[2000],
    )
    project_lifetime: int = Field(
        ..., ge=1, le=30,
        description="Evaluation horizon (years, max 30)",
        examples=[20],
    )

    # Schemes
    schemes: List[SchemeInput] = Field(
        ...,
        min_length=1,
        description=(
            "List of financing schemes to evaluate. Each entry is identified by scheme_type "
            "(discriminated union). At least one scheme is required."
        ),
    )

    # Output control
    output_level: OutputLevel = Field(
        ...,
        description=(
            "Output detail level set by the frontend tool context: "
            "private (homeowners), professional (consultants), "
            "public (institutions), complete (all fields)."
        ),
    )
    indicators: List[str] = Field(
        default=["IRR", "NPV", "PBP", "DPP", "ROI"],
        description="KPIs to include in the response.",
        examples=[["IRR", "NPV", "PBP"]],
    )
    include_visualizations: Optional[bool] = Field(
        default=None,
        description="Override to force include/exclude visualizations.",
    )

    @field_validator("indicators")
    @classmethod
    def validate_indicators(cls, v: List[str]) -> List[str]:
        valid = {"IRR", "NPV", "PBP", "DPP", "ROI"}
        invalid = set(v) - valid
        if invalid:
            raise ValueError(f"Invalid indicators: {invalid}. Must be one of: {valid}")
        if not v:
            raise ValueError("At least one indicator must be specified")
        return v

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "capex": 60000,
                    "annual_energy_savings": 27400,
                    "annual_maintenance_cost": 2000,
                    "project_lifetime": 20,
                    "output_level": "professional",
                    "schemes": [
                        {"scheme_type": "equity"},
                        {
                            "scheme_type": "bank_loan",
                            "loan_amount": 25000,
                            "term_years": 15,
                        },
                        {
                            "scheme_type": "epc_shared_savings",
                            "p_ESCO": 0.30,
                            "term_years": 10,
                        },
                    ],
                    "indicators": ["NPV", "IRR", "PBP", "ROI"],
                }
            ]
        }
    }


class RiskAssessmentResponse(BaseModel):
    """
    Response model for multi-scheme risk assessment.

    results is keyed by scheme_type and contains:
      - scheme_id, scheme_family
      - summary: percentiles (P5-P95) + probabilities + n_sims + disc_target_used
      - cashflow_distributions: per-year P5-P95 fan charts (private and above)
      - kpi_histograms: feasible/infeasible histograms (professional and above)
    """

    results: Dict[str, Any] = Field(
        ...,
        description="Per-scheme simulation results keyed by scheme_type.",
    )
    metadata: Dict[str, Any] = Field(
        ...,
        description="Global metadata: capex, project_lifetime, n_sims, output_level, etc.",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "results": {
                        "equity": {
                            "scheme_id": 1,
                            "scheme_family": "self_financed",
                            "summary": {
                                "percentiles": {
                                    "IRR": {"P5": 0.02, "P10": 0.03, "P50": 0.084, "P90": 0.14, "P95": 0.16},
                                    "NPV": {"P5": -2000, "P10": 1000, "P50": 15400, "P90": 32000, "P95": 38000},
                                },
                                "probabilities": {"Pr(NPV > 0)": 0.952, "Pr(PBP < 20y)": 0.971},
                                "disc_target_used": 0.05,
                                "n_sims": 10000,
                            },
                        }
                    },
                    "metadata": {
                        "capex": 60000,
                        "project_lifetime": 20,
                        "n_schemes": 1,
                        "output_level": "professional",
                    },
                }
            ]
        }
    }

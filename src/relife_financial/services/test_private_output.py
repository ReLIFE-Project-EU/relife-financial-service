"""Tests for private risk-assessment output."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from src.relife_financial.models.risk_assessment import (
    OutputLevel,
    RiskAssessmentRequest,
)
from src.relife_financial.services.risk_assessment import perform_risk_assessment


def _assert_private_result(response, scheme_type: str, scheme_family: str, lifetime: int) -> None:
    assert response.metadata["scheme_types"] == [scheme_type]
    result = response.results[scheme_type]
    assert result["scheme_family"] == scheme_family
    assert "P50" in result["summary"]["percentiles"]["NPV"]
    assert len(result["cashflow_distributions"]["years"]) == lifetime + 1
    assert "kpi_histograms" not in result


async def test_private_output_with_loan():
    request = RiskAssessmentRequest(
        capex=60000,
        annual_maintenance_cost=250,
        annual_energy_savings=27400,
        project_lifetime=20,
        schemes=[
            {
                "scheme_type": "bank_loan",
                "loan_amount": 20000,
                "term_years": 15,
            }
        ],
        output_level=OutputLevel.private,
    )

    response = await perform_risk_assessment(request)

    _assert_private_result(response, "bank_loan", "debt_financed", request.project_lifetime)


async def test_private_output_no_loan():
    request = RiskAssessmentRequest(
        capex=60000,
        annual_maintenance_cost=250,
        annual_energy_savings=27400,
        project_lifetime=20,
        schemes=[{"scheme_type": "equity"}],
        output_level=OutputLevel.private,
    )

    response = await perform_risk_assessment(request)

    _assert_private_result(response, "equity", "self_financed", request.project_lifetime)

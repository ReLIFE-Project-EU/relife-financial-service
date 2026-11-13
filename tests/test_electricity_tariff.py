"""HTTP contract and service-to-engine coverage for the optional electricity tariff."""

import httpx
import pytest

from relife_financial.app import app
from relife_financial.services import risk_assessment as risk_service


PAYLOAD = {
    "capex": 60000,
    "annual_energy_savings": 27400,
    "annual_maintenance_cost": 2000,
    "project_lifetime": 20,
    "output_level": "private",
    "schemes": [
        {"scheme_type": "equity"},
        {"scheme_type": "bank_loan", "loan_amount": 30000, "term_years": 10},
    ],
}


@pytest.fixture
def small_simulation(monkeypatch):
    """Keep the real HTTP/service/engine path, with fewer Monte Carlo draws."""
    engine = risk_service.get_kpi_results
    monkeypatch.setattr(risk_service, "get_kpi_results", lambda **kwargs: engine(**{**kwargs, "n_sims": 64}))


async def test_tariff_is_opt_in_and_preserves_the_response_contract(small_simulation):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        responses = [await client.post("/risk-assessment", json={**PAYLOAD, **extra}) for extra in (
            {}, {"electricity_tariff_eur_per_kwh": None},
            {"electricity_tariff_eur_per_kwh": 0.246}, {"electricity_tariff_eur_per_kwh": 0.30},
        )]

    assert [response.status_code for response in responses] == [200] * 4
    legacy, null, reference, changed = [response.json() for response in responses]
    assert legacy == null == reference
    assert changed.keys() == legacy.keys()
    assert changed["metadata"] == legacy["metadata"]
    # Fixed-seed values captured before introducing the new field.
    for scheme_type, expected_npv in (("equity", 12929.755155381004), ("bank_loan", 14682.306900570646)):
        old_npv = legacy["results"][scheme_type]["summary"]["percentiles"]["NPV"]["P50"]
        assert old_npv == pytest.approx(expected_npv, rel=1e-10)
        assert changed["results"][scheme_type].keys() == legacy["results"][scheme_type].keys()
        assert changed["results"][scheme_type]["summary"]["percentiles"]["NPV"]["P50"] > old_npv


@pytest.mark.parametrize("tariff", [0, -0.1, "not-a-price", "NaN", "Infinity", "-Infinity"])
async def test_invalid_tariff_returns_422_before_simulation(tariff, monkeypatch):
    def unexpected_simulation(**kwargs):
        pytest.fail("Invalid electricity tariff reached the simulation engine")

    monkeypatch.setattr(risk_service, "get_kpi_results", unexpected_simulation)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/risk-assessment", json={**PAYLOAD, "electricity_tariff_eur_per_kwh": tariff},
        )

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "electricity_tariff_eur_per_kwh"]

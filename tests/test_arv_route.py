"""
Regression test for POST /arv.

Pins the route to the migrated ARVRequest/ARVResponse schema:
- ARVRequest no longer has `energy_class`.
- ARVResponse exposes prices under `after`/`before` snapshots, not at the top level.

The service layer is monkeypatched so the test runs offline (no ML model load).
"""

from fastapi.testclient import TestClient

from relife_financial.app import app
from relife_financial.models.arv import ARVResponse, ARVValueSnapshot
from relife_financial.routes import arv as arv_route


client = TestClient(app)


VALID_PAYLOAD = {
    "lat": 41.9028,
    "lng": 12.4964,
    "floor_area": 260,
    "construction_year": 1930,
    "number_of_floors": 3,
    "floor_number": 1,
    "property_type": "Detached House",
    "target_country": "Italy",
    "energy_consumption_after": 1119.6153846153845,
    "renovated_last_5_years": False,
}


def _fake_response(floor_area: float) -> ARVResponse:
    return ARVResponse(
        after=ARVValueSnapshot(
            price_per_sqm=1234.56,
            total_price=1234.56 * floor_area,
            greek_epc_class="Ε",
            epc_resolution={
                "target_country": "Italy",
                "source_epc_class": "E",
                "italy_epc_class": "E",
                "greek_epc_class": "Ε",
            },
        ),
        before=None,
        uplift=None,
        floor_area=floor_area,
        metadata={"model_file": "test", "building_age": 96},
    )


def test_post_arv_with_migrated_schema_returns_nested_response(monkeypatch):
    async def fake_predict_arv(request):
        return _fake_response(request.floor_area)

    # Patch the route-module-local binding (the route did
    # `from ...services.arv import predict_arv` at import time),
    # not the service module's symbol.
    monkeypatch.setattr(arv_route, "predict_arv", fake_predict_arv)

    response = client.post("/arv", json=VALID_PAYLOAD)

    assert response.status_code == 200, response.text

    body = response.json()
    assert "after" in body
    assert body["after"]["price_per_sqm"] == 1234.56
    assert body["after"]["total_price"] == 1234.56 * VALID_PAYLOAD["floor_area"]
    assert body["after"]["greek_epc_class"] == "Ε"
    assert body["before"] is None
    assert body["uplift"] is None
    assert body["floor_area"] == VALID_PAYLOAD["floor_area"]

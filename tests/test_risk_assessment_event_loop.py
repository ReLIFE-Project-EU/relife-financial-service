"""
Regression test: POST /risk-assessment must not block the event loop.

The Monte Carlo engine is CPU-bound. Run directly on the event loop, it froze
every concurrent request for its whole duration (about 10 s), so concurrent
token checks timed out and surfaced as 401 responses.

The engine is replaced by a stub that waits for /health to be served. That can
only happen if the engine runs off the event loop.
"""

import asyncio
import threading

import httpx

from relife_financial.app import app
from relife_financial.services import risk_assessment as risk_service

# Upper bound for each wait, so a regression fails instead of hanging.
WAIT_SECONDS = 5

PAYLOAD = {
    "capex": 10000,
    "annual_energy_savings": 1000,
    "annual_maintenance_cost": 100,
    "project_lifetime": 20,
    "output_level": "private",
    "schemes": [{"scheme_type": "equity"}],
    "indicators": ["NPV"],
}


async def test_risk_assessment_does_not_block_other_requests(monkeypatch):
    engine_started = threading.Event()
    health_served = threading.Event()
    engine_saw_health: list[bool] = []

    def engine_waiting_for_health(**_kwargs):
        engine_started.set()
        engine_saw_health.append(health_served.wait(timeout=WAIT_SECONDS))
        raise RuntimeError("stubbed engine")

    monkeypatch.setattr(risk_service, "get_kpi_results", engine_waiting_for_health)

    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        risk = asyncio.create_task(client.post("/risk-assessment", json=PAYLOAD))
        assert await asyncio.to_thread(engine_started.wait, WAIT_SECONDS)

        health = await client.get("/health")
        health_served.set()
        await risk

    assert health.status_code == 200
    assert engine_saw_health == [True]

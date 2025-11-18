from fastapi.testclient import TestClient

from relife_financial.app import app

client = TestClient(app)


def test_health_check():
    """Test the basic health check endpoint."""

    response = client.get("/health")

    assert response.status_code == 200

    data = response.json()

    assert "status" in data
    assert "timestamp" in data
    assert data["status"] == "healthy"
    assert isinstance(data["timestamp"], int)

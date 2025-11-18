from unittest.mock import patch

from fastapi.testclient import TestClient

from relife_financial.app import app

client = TestClient(app)


@patch("relife_financial.config.settings.get_settings")
def test_storage_endpoints_require_authentication(mock_get_settings, mock_settings):
    """Test that storage endpoints require authentication."""

    mock_get_settings.return_value = mock_settings

    # Test upload endpoint
    response = client.post("/storage")
    assert response.status_code in [401, 403, 422]  # 422 for missing file

    # Test list endpoint
    response = client.get("/storage")
    assert response.status_code in [401, 403]

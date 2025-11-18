from unittest.mock import patch

from fastapi.testclient import TestClient

from relife_financial.app import app

client = TestClient(app)


@patch("relife_financial.config.settings.get_settings")
def test_whoami_without_authentication(mock_get_settings, mock_settings):
    """Test that /whoami endpoint requires authentication."""

    mock_get_settings.return_value = mock_settings
    response = client.get("/whoami")

    # Should return 401 or 403 for unauthenticated requests
    assert response.status_code in [401, 403]

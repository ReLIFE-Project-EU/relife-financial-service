from fastapi.testclient import TestClient

from relife_financial.app import app

client = TestClient(app)


def test_app_creation():
    """Test that the FastAPI app is created correctly."""

    assert app.title
    assert app.description
    assert hasattr(app, "version")


def test_openapi_docs_available():
    """Test that OpenAPI documentation is available."""

    response = client.get("/docs")
    assert response.status_code == 200

    response = client.get("/openapi.json")
    assert response.status_code == 200

    openapi_data = response.json()
    assert "openapi" in openapi_data
    assert openapi_data["info"]["title"]

def test_openapi_docs_npv_available():
    """Test that OpenAPI documentation for the NPV endpoint is available."""

    response = client.get("/openapi.json")
    assert response.status_code == 200

    openapi_data = response.json()
    assert "/financial/npv" in openapi_data["paths"]
    npv_post = openapi_data["paths"]["/financial/npv"]["post"]
    assert "summary" in npv_post
    assert "net present value" in npv_post["summary"].lower()
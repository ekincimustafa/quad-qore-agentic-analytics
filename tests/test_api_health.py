from fastapi.testclient import TestClient

from app.api.main import APP_VERSION, create_app


client = TestClient(create_app())


def test_health_endpoint_returns_expected_response():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "quad-qore-api",
        "version": APP_VERSION,
    }


def test_openapi_schema_contains_health_endpoint():
    response = client.get("/openapi.json")

    assert response.status_code == 200

    schema = response.json()

    assert schema["info"]["title"] == "Quad-Qore Agentic Analytics API"
    assert schema["info"]["version"] == APP_VERSION
    assert "/health" in schema["paths"]


def test_swagger_documentation_is_available():
    response = client.get("/docs")

    assert response.status_code == 200
    assert "swagger" in response.text.lower()
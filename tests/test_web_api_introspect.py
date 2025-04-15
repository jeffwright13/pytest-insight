"""Tests for the pytest-insight introspective API (dynamic FastAPI endpoints)."""

from fastapi.testclient import TestClient

# Import the introspected app
from pytest_insight.rest_api.introspective_api import introspected_app

client = TestClient(introspected_app)


def test_docs_available():
    resp = client.get("/docs")
    assert resp.status_code == 200
    assert "Swagger UI" in resp.text or "swagger-ui" in resp.text

    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    assert resp.json()["openapi"].startswith("3")


def test_category_index():
    resp = client.get("/api/categories")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, dict)
    assert any("Query" in k or "query" in k for k in data.keys())


def test_query_recent_sessions():
    resp = client.get("/api/operations/query/recent")
    assert resp.status_code == 200
    data = resp.json()
    assert "sessions" in data
    assert isinstance(data["sessions"], list)


def test_execute_query():
    # This endpoint is a placeholder but should return results
    resp = client.post("/api/operations/query/execute", json={"filter": "all"})
    assert resp.status_code == 200
    data = resp.json()
    assert "results" in data or "sessions" in data
    if "results" in data:
        if isinstance(data["results"], list):
            assert True
        elif isinstance(data["results"], dict) and "sessions" in data["results"]:
            assert isinstance(data["results"]["sessions"], list)
        else:
            assert False, f"Unexpected results structure: {data['results']}"
    if "sessions" in data:
        assert isinstance(data["sessions"], list)


def test_invalid_endpoint_returns_404():
    resp = client.get("/api/doesnotexist")
    assert resp.status_code == 404
    assert "Not Found" in resp.text


def test_invalid_query_input():
    # Send bad input to a known endpoint
    resp = client.post("/api/operations/query/execute", json={"filter": 12345})
    # Should still succeed but results may be empty or error handled
    assert resp.status_code == 200
    assert "results" in resp.json()

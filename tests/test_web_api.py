"""Integration tests for FastAPI Web API routes."""

import pytest
from fastapi.testclient import TestClient
from gxp_rag.web.app import app


@pytest.fixture
def client():
    return TestClient(app)


def test_index_page(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "AI GxP Document Draft Studio" in response.text


def test_api_presets(client):
    response = client.get("/api/presets")
    assert response.status_code == 200
    data = response.json()
    assert "presets" in data
    assert len(data["presets"]) >= 5


def test_api_stats(client):
    response = client.get("/api/stats")
    assert response.status_code == 200
    data = response.json()
    assert "qdrant" in data


def test_api_search(client):
    response = client.post("/api/search", json={"query": "cleanroom", "limit": 3})
    assert response.status_code == 200
    data = response.json()
    assert "results" in data


def test_api_audit_and_integrity(client):
    response = client.get("/api/audit")
    assert response.status_code == 200
    data = response.json()
    assert "integrity" in data
    assert data["integrity"]["valid"] is True

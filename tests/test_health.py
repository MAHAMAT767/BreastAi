"""Tests de fumée de l'API : l'application démarre et répond."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_root_returns_metadata(client: TestClient) -> None:
    response = client.get("/")

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "BreastAI"
    assert "version" in body


def test_root_carries_medical_disclaimer(client: TestClient) -> None:
    """Le disclaimer doit rester exposé : c'est une exigence produit, pas cosmétique."""
    body = client.get("/").json()

    assert "disclaimer" in body
    assert "ne remplacent pas l'avis" in body["disclaimer"]


def test_liveness_probe(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_api_v1_health(client: TestClient) -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["app_name"] == "BreastAI"
    assert "environment" in body


def test_openapi_schema_is_generated(client: TestClient) -> None:
    response = client.get("/openapi.json")

    assert response.status_code == 200
    assert response.json()["info"]["title"] == "BreastAI"

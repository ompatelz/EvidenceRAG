"""Tests for the minimal operational API slice."""

from fastapi.testclient import TestClient

from evidence_rag import __version__
from evidence_rag.api import create_app
from evidence_rag.config import AppSettings


def test_health_response_is_stable() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": __version__}


def test_ready_when_local_configuration_is_valid() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_not_ready_with_explicit_test_configuration() -> None:
    settings = AppSettings(app_name="EvidenceRAG Test", environment="test", ready=False)
    app = create_app(settings)

    with TestClient(app) as client:
        response = client.get("/ready")

    assert app.title == "EvidenceRAG Test"
    assert response.status_code == 503
    assert response.json() == {"status": "not_ready"}

"""Behavioural tests for every public endpoint in the TA1 API."""

from fastapi.testclient import TestClient

from app.main import APP_NAME, APP_VERSION, app

client = TestClient(app)


def test_root_identifies_application() -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["application"] == APP_NAME
    assert response.json()["version"] == APP_VERSION


def test_health_is_cheap_and_healthy() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_metrics_info_contains_pod_context() -> None:
    response = client.get("/metrics-info")
    assert response.status_code == 200
    assert "pod_name" in response.json()
    assert response.json()["maximum_cpu_duration_ms"] == 2_000


def test_cpu_load_is_bounded_and_reports_work() -> None:
    response = client.get("/cpu", params={"duration_ms": 10})
    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "completed"
    assert body["requested_duration_ms"] == 10
    assert body["elapsed_ms"] >= 9
    assert body["iterations"] > 0


def test_cpu_load_rejects_out_of_range_values() -> None:
    assert client.get("/cpu", params={"duration_ms": 9}).status_code == 422
    assert client.get("/cpu", params={"duration_ms": 2001}).status_code == 422

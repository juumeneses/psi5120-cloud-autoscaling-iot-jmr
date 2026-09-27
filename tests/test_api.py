"""Behavioural tests for the autoscaling and final IoT API endpoints."""

import io
from decimal import Decimal

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


class FakeTable:
    """Small DynamoDB test double that never reaches an AWS account."""

    def query(self, **kwargs):
        assert kwargs["ScanIndexForward"] is False
        return {"Items": [{"device_id": "psi5120-final-jmr-device01", "sequence": Decimal(1001)}]}


class FakeIoTData:
    """IoT data-plane test double for publish and shadow operations."""

    def publish(self, **kwargs):
        assert kwargs["qos"] == 1

    def get_thing_shadow(self, **kwargs):
        return {"payload": io.BytesIO(b'{"state":{"reported":{"target_temperature":15}}}')}

    def update_thing_shadow(self, **kwargs):
        assert b"target_temperature" in kwargs["payload"]


def test_recent_telemetry_is_json_safe(monkeypatch) -> None:
    monkeypatch.setattr("app.main.dynamodb_table", lambda: FakeTable())
    response = client.get("/telemetry", params={"limit": 3})
    assert response.status_code == 200
    assert response.json()["items"][0]["sequence"] == 1001


def test_cloud_to_device_command(monkeypatch) -> None:
    monkeypatch.setattr("app.main.iot_data_client", lambda: FakeIoTData())
    response = client.post("/commands", params={"command": "fan-on"})
    assert response.status_code == 200
    assert response.json()["status"] == "published"


def test_shadow_read_and_desired_update(monkeypatch) -> None:
    monkeypatch.setattr("app.main.iot_data_client", lambda: FakeIoTData())
    assert client.get("/device-shadow").status_code == 200
    response = client.post("/device-shadow/desired", params={"target_temperature": 15})
    assert response.status_code == 200
    assert response.json()["state"]["desired"]["target_temperature"] == 15

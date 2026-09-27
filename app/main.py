"""HTTP API used to compare Kubernetes HPA behaviour in Minikube and EKS."""

from __future__ import annotations

import hashlib
import os
import json
import time
from decimal import Decimal
from typing import Final

import boto3

from fastapi import FastAPI, Query

APP_NAME: Final[str] = "psi5120-cloud-autoscaling-api"
APP_VERSION: Final[str] = "2.0.0-final"
MAX_CPU_DURATION_MS: Final[int] = 2_000

app = FastAPI(
    title="PSI5120 Cloud Autoscaling API",
    version=APP_VERSION,
    description="An autoscaled API integrating Kubernetes with AWS IoT and DynamoDB.",
)


def aws_settings() -> dict[str, str]:
    """Return non-secret AWS resource names supplied through the environment."""
    return {
        "region": os.getenv("AWS_REGION", "us-east-1"),
        "table": os.getenv("TELEMETRY_TABLE", "psi5120-final-jmr-telemetry"),
        "thing": os.getenv("IOT_THING_NAME", "psi5120-final-jmr-device01"),
        "command_topic": os.getenv(
            "IOT_COMMAND_TOPIC", "psi5120/final/psi5120-final-jmr-device01/command"
        ),
    }


def dynamodb_table():
    """Create the DynamoDB table handle using the standard AWS credential chain."""
    settings = aws_settings()
    return boto3.resource("dynamodb", region_name=settings["region"]).Table(settings["table"])


def iot_data_client():
    """Create an IoT Data client without embedding credentials in the image."""
    return boto3.client("iot-data", region_name=aws_settings()["region"])


def json_safe(value: object) -> object:
    """Convert DynamoDB Decimal values into ordinary JSON number values."""
    if isinstance(value, Decimal):
        return int(value) if value % 1 == 0 else float(value)
    if isinstance(value, list):
        return [json_safe(item) for item in value]
    if isinstance(value, dict):
        return {key: json_safe(item) for key, item in value.items()}
    return value


def pod_identity() -> dict[str, str]:
    """Return non-sensitive runtime identifiers useful for distribution evidence."""
    return {
        "pod_name": os.getenv("POD_NAME", os.getenv("HOSTNAME", "local")),
        "namespace": os.getenv("POD_NAMESPACE", "local"),
        "node_name": os.getenv("NODE_NAME", "local"),
    }


@app.get("/", tags=["application"])
def root() -> dict[str, object]:
    """Describe the application and expose the pod serving the request."""
    return {
        "application": APP_NAME,
        "version": APP_VERSION,
        "environment": os.getenv("APP_ENV", "development"),
        "iot_extension": True,
        **pod_identity(),
    }


@app.get("/telemetry", tags=["iot"])
def recent_telemetry(limit: int = Query(default=10, ge=1, le=100)) -> dict[str, object]:
    """Return the newest readings for the configured simulated IoT thing."""
    settings = aws_settings()
    response = dynamodb_table().query(
        KeyConditionExpression="device_id = :device_id",
        ExpressionAttributeValues={":device_id": settings["thing"]},
        ScanIndexForward=False,
        Limit=limit,
    )
    return {"device_id": settings["thing"], "items": json_safe(response.get("Items", []))}


@app.post("/commands", tags=["iot"])
def publish_command(command: str = Query(min_length=1, max_length=40)) -> dict[str, str]:
    """Publish a cloud-to-device command to the least-privilege command topic."""
    settings = aws_settings()
    payload = {"command_id": f"cmd-{int(time.time())}", "command": command}
    iot_data_client().publish(
        topic=settings["command_topic"], qos=1, payload=json.dumps(payload).encode("utf-8")
    )
    return {"status": "published", "topic": settings["command_topic"], **payload}


@app.get("/device-shadow", tags=["iot"])
def get_device_shadow() -> dict[str, object]:
    """Read the simulated device shadow through the AWS IoT data plane."""
    response = iot_data_client().get_thing_shadow(thingName=aws_settings()["thing"])
    return json.loads(response["payload"].read())


@app.post("/device-shadow/desired", tags=["iot"])
def set_desired_state(target_temperature: int = Query(ge=10, le=35)) -> dict[str, object]:
    """Request a bounded actuator target through Device Shadow desired state."""
    payload = {"state": {"desired": {"target_temperature": target_temperature}}}
    iot_data_client().update_thing_shadow(
        thingName=aws_settings()["thing"], payload=json.dumps(payload).encode("utf-8")
    )
    return {"status": "desired-state-published", **payload}


@app.get("/health", tags=["operations"])
def health() -> dict[str, str]:
    """Provide a low-cost endpoint for Kubernetes liveness and readiness probes."""
    return {"status": "healthy"}


@app.get("/metrics-info", tags=["operations"])
def metrics_info() -> dict[str, object]:
    """Expose configuration relevant to an HPA experiment without leaking secrets."""
    return {
        **pod_identity(),
        "cpu_count": os.cpu_count() or 1,
        "maximum_cpu_duration_ms": MAX_CPU_DURATION_MS,
        "monotonic_timestamp_s": round(time.monotonic(), 3),
    }


@app.get("/cpu", tags=["experiment"])
def cpu_load(
    duration_ms: int = Query(
        default=250,
        ge=10,
        le=MAX_CPU_DURATION_MS,
        description="Approximate CPU work duration for this request.",
    ),
) -> dict[str, object]:
    """Consume CPU for a bounded interval so the HPA receives reproducible pressure."""
    started = time.perf_counter()
    deadline = started + (duration_ms / 1_000)
    iterations = 0
    digest = b"psi5120"

    # Hashing is intentionally CPU-bound, deterministic, bounded and side-effect free.
    while time.perf_counter() < deadline:
        digest = hashlib.sha256(digest).digest()
        iterations += 1

    elapsed_ms = round((time.perf_counter() - started) * 1_000, 2)
    return {
        "status": "completed",
        "requested_duration_ms": duration_ms,
        "elapsed_ms": elapsed_ms,
        "iterations": iterations,
        "checksum_prefix": digest.hex()[:12],
        **pod_identity(),
    }

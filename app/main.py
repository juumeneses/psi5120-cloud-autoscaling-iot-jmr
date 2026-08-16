"""HTTP API used to compare Kubernetes HPA behaviour in Minikube and EKS."""

from __future__ import annotations

import hashlib
import os
import time
from typing import Final

from fastapi import FastAPI, Query

APP_NAME: Final[str] = "psi5120-cloud-autoscaling-api"
APP_VERSION: Final[str] = "1.0.0-ta1"
MAX_CPU_DURATION_MS: Final[int] = 2_000

app = FastAPI(
    title="PSI5120 Cloud Autoscaling API",
    version=APP_VERSION,
    description="A deterministic CPU-load API for comparing HPA on Minikube and EKS.",
)


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
        **pod_identity(),
    }


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

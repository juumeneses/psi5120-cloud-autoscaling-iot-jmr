"""AWS IoT Rule target that validates and persists simulated telemetry."""

from __future__ import annotations

import os
from decimal import Decimal

import boto3

TABLE_NAME = os.getenv("TELEMETRY_TABLE", "psi5120-final-jmr-telemetry")
TABLE = boto3.resource("dynamodb").Table(TABLE_NAME)


def lambda_handler(event: dict, context: object) -> dict:
    """Persist one validated MQTT reading with a deterministic composite key."""
    required = {"device_id", "sequence", "temperature_c", "timestamp_utc"}
    missing = sorted(required.difference(event))
    if missing:
        raise ValueError(f"Missing telemetry fields: {', '.join(missing)}")

    item = {
        "device_id": str(event["device_id"]),
        "sequence": int(event["sequence"]),
        "temperature_c": Decimal(str(event["temperature_c"])),
        "humidity_percent": Decimal(str(event.get("humidity_percent", 0))),
        "actuator_state": str(event.get("actuator_state", "off")),
        "timestamp_utc": str(event["timestamp_utc"]),
    }
    TABLE.put_item(Item=item)
    print({"event": "dynamodb_put_ok", "device_id": item["device_id"], "sequence": item["sequence"]})
    return {"statusCode": 200, "device_id": item["device_id"], "sequence": item["sequence"]}

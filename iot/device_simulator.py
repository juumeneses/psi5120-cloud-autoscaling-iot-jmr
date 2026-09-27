#!/usr/bin/env python3
"""Software-only temperature sensor and actuator for AWS IoT Core.

The client authenticates with X.509 mTLS, publishes deterministic telemetry,
receives commands, and converges Device Shadow desired state into reported state.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from awscrt import mqtt
from awsiot import mqtt_connection_builder

STOP = threading.Event()


def utc_now() -> str:
    """Return an ISO 8601 timestamp suitable for evidence and persistence."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def compact_json(value: object) -> str:
    """Serialize MQTT payloads consistently without losing Unicode text."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def required_file(path: str, label: str) -> None:
    """Fail before connecting if one of the mTLS files is absent."""
    if not Path(path).is_file():
        raise FileNotFoundError(f"{label} not found: {path}")


def connection_for(args):
    """Build a mutual-TLS MQTT connection with reconnect diagnostics."""
    def interrupted(connection, error, **kwargs):
        print(f"[CONNECTION_INTERRUPTED] error={error}", flush=True)

    def resumed(connection, return_code, session_present, **kwargs):
        print(f"[CONNECTION_RESUMED] code={return_code} session={session_present}", flush=True)
        if return_code == mqtt.ConnectReturnCode.ACCEPTED and not session_present:
            connection.resubscribe_existing_topics()[0].result(timeout=10)

    return mqtt_connection_builder.mtls_from_path(
        endpoint=args.endpoint,
        cert_filepath=args.cert,
        pri_key_filepath=args.key,
        ca_filepath=args.ca,
        client_id=args.thing_name,
        clean_session=True,
        keep_alive_secs=30,
        on_connection_interrupted=interrupted,
        on_connection_resumed=resumed,
    )


def publish(connection, topic: str, payload: dict, label: str) -> None:
    """Publish at QoS 1 and wait for acknowledgement."""
    connection.publish(topic=topic, payload=compact_json(payload), qos=mqtt.QoS.AT_LEAST_ONCE)[0].result(timeout=10)
    print(f"[PUBLISH_OK] label={label} topic={topic} payload={compact_json(payload)}", flush=True)


def subscribe(connection, topic: str, callback, label: str) -> None:
    """Subscribe at QoS 1 and reject a failure SUBACK (0x80)."""
    result = connection.subscribe(topic=topic, qos=mqtt.QoS.AT_LEAST_ONCE, callback=callback)[0].result(timeout=10)
    if result.get("qos") == 0x80:
        raise RuntimeError(f"SUBSCRIBE denied for {topic}")
    print(f"[SUBSCRIBE_OK] label={label} topic={topic}", flush=True)


def run(args) -> int:
    """Run telemetry, commands, and shadow synchronization in one session."""
    for path, label in [(args.cert, "certificate"), (args.key, "private key"), (args.ca, "root CA")]:
        required_file(path, label)

    prefix = f"psi5120/final/{args.thing_name}"
    telemetry_topic = f"{prefix}/telemetry"
    command_topic = f"{prefix}/command"
    shadow_delta_topic = f"$aws/things/{args.thing_name}/shadow/update/delta"
    shadow_update_topic = f"$aws/things/{args.thing_name}/shadow/update"
    connection = connection_for(args)
    connection.connect().result(timeout=15)
    print(f"[CONNECTED] client_id={args.thing_name} time={utc_now()}", flush=True)

    actuator = {"state": "off", "target_temperature": 22}

    def on_command(topic, payload, **kwargs):
        document = json.loads(payload.decode("utf-8"))
        actuator["state"] = document.get("command", actuator["state"])
        print(f"[COMMAND_RECEIVED] topic={topic} payload={compact_json(document)}", flush=True)

    def on_shadow_delta(topic, payload, **kwargs):
        desired = json.loads(payload.decode("utf-8")).get("state", {})
        actuator.update(desired)
        print(f"[SHADOW_DELTA] desired={compact_json(desired)}", flush=True)

        # Never block the SDK callback thread while waiting for a publish ACK.
        def report() -> None:
            publish(connection, shadow_update_topic, {"state": {"reported": desired}}, "shadow_reported")
            print(f"[SHADOW_REPORTED] state={compact_json(desired)}", flush=True)

        threading.Thread(target=report, daemon=True).start()

    subscribe(connection, command_topic, on_command, "command")
    subscribe(connection, shadow_delta_topic, on_shadow_delta, "shadow_delta")
    publish(connection, shadow_update_topic, {"state": {"reported": {"simulator_online": True}}}, "shadow_online")

    for sequence in range(1001, 1001 + args.count):
        if STOP.is_set():
            break
        reading = {
            "device_id": args.thing_name,
            "sequence": sequence,
            "temperature_c": round(21.5 + (sequence - 1000) * 0.3, 1),
            "humidity_percent": 54 + (sequence % 3),
            "actuator_state": actuator["state"],
            "timestamp_utc": utc_now(),
        }
        publish(connection, telemetry_topic, reading, "telemetry")
        STOP.wait(args.interval)

    deadline = time.monotonic() + args.listen_seconds
    while not STOP.is_set() and time.monotonic() < deadline:
        STOP.wait(0.5)

    publish(connection, shadow_update_topic, {"state": {"reported": {"simulator_online": False}}}, "shadow_offline")
    connection.disconnect().result(timeout=10)
    print("[DISCONNECTED]", flush=True)
    return 0


def forbidden_subscribe(args) -> int:
    """Prove least privilege by attempting a topic absent from the policy."""
    connection = connection_for(args)
    connection.connect().result(timeout=15)
    topic = f"psi5120/final/{args.thing_name}/forbidden/#"
    try:
        result = connection.subscribe(topic=topic, qos=mqtt.QoS.AT_LEAST_ONCE, callback=lambda **_: None)[0].result(timeout=10)
        denied = result.get("qos") == 0x80
    except Exception as error:
        denied = True
        print(f"[EXPECTED_AUTHORIZATION_FAILURE] {type(error).__name__}: {error}", flush=True)
    finally:
        try:
            connection.disconnect().result(timeout=10)
        except Exception:
            pass
    if not denied:
        print("[UNEXPECTED_AUTHORIZATION_SUCCESS]", flush=True)
        return 2
    print(f"[EXPECTED_AUTHORIZATION_FAILURE] SUBSCRIBE denied for {topic}", flush=True)
    return 0


def arguments() -> argparse.Namespace:
    """Parse explicit arguments while supporting container environment variables."""
    parser = argparse.ArgumentParser(description="PSI5120 software-only AWS IoT device")
    parser.add_argument("mode", choices=["run", "forbidden-subscribe"])
    parser.add_argument("--endpoint", default=os.getenv("IOT_ENDPOINT"))
    parser.add_argument("--thing-name", default=os.getenv("THING_NAME"))
    parser.add_argument("--cert", default="certs/device.pem.crt")
    parser.add_argument("--key", default="certs/private.pem.key")
    parser.add_argument("--ca", default="certs/AmazonRootCA1.pem")
    parser.add_argument("--count", type=int, default=3)
    parser.add_argument("--interval", type=int, default=5)
    parser.add_argument("--listen-seconds", type=int, default=120)
    return parser.parse_args()


def main() -> int:
    """Validate configuration and dispatch the requested evidence mode."""
    args = arguments()
    if not args.endpoint or not args.thing_name:
        raise ValueError("IOT_ENDPOINT and THING_NAME are required")
    signal.signal(signal.SIGINT, lambda *_: STOP.set())
    signal.signal(signal.SIGTERM, lambda *_: STOP.set())
    return run(args) if args.mode == "run" else forbidden_subscribe(args)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"[FATAL] {type(error).__name__}: {error}", file=sys.stderr, flush=True)
        raise SystemExit(1)

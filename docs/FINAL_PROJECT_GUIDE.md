# Final Project Reproduction Guide

## Scope

This is option 2.2: an extension of the intermediate Kubernetes/HPA project.
The device is a software simulator, so no ESP32, Raspberry Pi, sensor, or other
physical equipment is used. AWS resources use region `us-east-1` and the `jmr`
identifier. The intermediate version remains reproducible from tag
`ta1-submission`.

## Architecture

1. The Python device authenticates to AWS IoT Core with an X.509 certificate.
2. MQTT telemetry is published at QoS 1 to a device-specific topic.
3. an IoT SQL rule invokes Lambda for each reading.
4. Lambda validates the event and writes it to DynamoDB.
5. FastAPI reads recent telemetry, publishes device commands, and manages the
   Device Shadow through AWS APIs.
6. Kubernetes retains the HPA from TA1 and scales API pods under `/cpu` load.

## Local validation

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
docker build -t psi5120-autoscaling-api:2.0.0-final .
docker build -t psi5120-iot-device:2.0.0-final iot/
kubectl apply --dry-run=client -k k8s/overlays/final
```

## AWS provisioning

Use AWS CloudShell from `us-east-1`; it supplies temporary console credentials
without copying access keys to the repository.

```bash
git clone https://github.com/juumeneses/psi5120-cloud-autoscaling-iot-jmr.git
cd psi5120-cloud-autoscaling-iot-jmr
bash aws/setup_final.sh
```

The final line prints the account-specific IoT data endpoint. Export it only in
the CloudShell session:

```bash
export IOT_ENDPOINT="YOUR_ENDPOINT_HERE"
export THING_NAME="psi5120-final-jmr-device01"
python3 -m pip install --user -r iot/requirements.txt
cd iot
python3 device_simulator.py run --count 3 --interval 3 --listen-seconds 180 | tee ../evidence/final/device-session.txt
```

While the simulator is listening, publish a command through the IoT MQTT test
client or FastAPI and set Shadow desired state to `target_temperature=15`.
The output must show `COMMAND_RECEIVED`, `SHADOW_DELTA`, and `SHADOW_REPORTED`.
Then execute the negative authorization test:

```bash
python3 device_simulator.py forbidden-subscribe | tee ../evidence/final/authorization-test.txt
```

## Persistence and API validation

```bash
aws dynamodb query --region us-east-1 \
  --table-name psi5120-final-jmr-telemetry \
  --key-condition-expression "device_id = :d" \
  --expression-attribute-values '{":d":{"S":"psi5120-final-jmr-device01"}}'

aws logs tail /aws/lambda/psi5120-final-jmr-ingest \
  --region us-east-1 --since 15m
```

For a workstation or pod with an AWS role granting only DynamoDB Query and IoT
data-plane actions, configure the four non-secret environment variables shown
in `k8s/overlays/final/deployment-iot-env.yaml` and exercise:

- `GET /telemetry?limit=3`;
- `POST /commands?command=fan-on`;
- `GET /device-shadow`;
- `POST /device-shadow/desired?target_temperature=15`.

## Kubernetes/HPA validation

The TA1 load methodology is deliberately unchanged, allowing a controlled
before/after comparison. Load the final image into Minikube, apply the overlay,
and run three cycles:

```bash
minikube image load psi5120-autoscaling-api:2.0.0-final
kubectl apply -k k8s/overlays/final
kubectl -n psi5120-ta1 wait deployment/autoscaling-api --for=condition=Available --timeout=180s
./scripts/run_hpa_experiment.sh final-run-1
./scripts/run_hpa_experiment.sh final-run-2
./scripts/run_hpa_experiment.sh final-run-3
```

Record time to first scale-out, peak replicas, peak CPU, and scale-down time.
The HPA acceptance criterion is an increase from one to multiple pods followed
by recovery to one after the load stops.

## Evidence checklist

- Thing, active certificate metadata, and least-privilege policy (never the key);
- MQTT connection and three QoS 1 telemetry publishes;
- command received by the simulator;
- desired Shadow state converging to reported state;
- denied subscription to the forbidden topic;
- IoT Rule, successful Lambda log, and three DynamoDB items;
- FastAPI telemetry and command responses;
- HPA before, during, and after load;
- sanitized cost and resource summaries.

## Cleanup

Only after the screenshots, text logs, article, and repository have been
reviewed, run `bash aws/cleanup_final.sh`. Confirm in the console that the named
Thing, certificate, rule, Lambda function, DynamoDB table, IAM role, and log
group no longer require attention. Never commit the `iot/certs` directory.

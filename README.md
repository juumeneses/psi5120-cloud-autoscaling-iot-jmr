# PSI5120 Cloud Autoscaling API

Individual project by **Julia Meneses Roberto** for PSI512 — Cloud Computing
Topics (2026).

This repository contains the completed first evaluative assignment and its
final-project extension. The immutable `ta1-submission` tag contains the
Minikube/EKS HPA comparison. The current version adds a software-only IoT
device, AWS IoT Core, Lambda, DynamoDB, Device Shadow, and cloud-to-device
commands while retaining the autoscaled FastAPI workload.

## TA1 contents

- FastAPI application and five endpoint tests;
- non-root, reproducible Docker image;
- commented Kubernetes Deployment, Service, HPA, and load generator;
- Minikube and EKS overlays;
- scripts for three timestamped experiments per environment;
- deployment, evidence, troubleshooting, and cleanup documentation;
- IEEE article and sanitized evidence after the practical runs.

## Quick validation

```bash
python -m pytest -v
docker build -t psi5120-autoscaling-api:1.0.0-ta1 .
kubectl apply --dry-run=client -k k8s/overlays/minikube
```

See `docs/DEPLOYMENT_AND_TEST_GUIDE.md` for the complete procedure.

## Final-project extension (option 2.2)

- `iot/device_simulator.py`: X.509 mTLS MQTT device, deterministic sensor data,
  simulated actuator, commands, shadow convergence, and authorization test;
- `iot/lambda_function.py`: validated, least-privilege telemetry persistence;
- `app/main.py`: DynamoDB query, IoT command, and Device Shadow endpoints;
- `aws/`: reviewed provisioning, IAM policy, and cleanup automation;
- `k8s/overlays/final`: version 2 API with the original CPU-based HPA.

No physical sensor is required: sensor readings and actuator state are generated
by the containerized Python client. See `docs/FINAL_PROJECT_GUIDE.md` for the
complete reproducible procedure and evidence checklist.

```bash
python -m pytest -q
docker build -t psi5120-autoscaling-api:2.0.0-final .
docker build -t psi5120-iot-device:2.0.0-final iot/
kubectl apply --dry-run=client -k k8s/overlays/final
```

## Security

Never commit AWS credentials, kubeconfig files, private keys, certificates, or
raw screenshots that expose account details. The `.gitignore` blocks the most
common secret formats, but every artefact must also be reviewed manually.

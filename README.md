# PSI5120 Cloud Autoscaling API

Individual project by **Julia Meneses Roberto** for PSI512 — Cloud Computing
Topics (2026).

This repository contains the complete first evaluative assignment: the same
commented FastAPI workload deployed with a CPU-based Kubernetes Horizontal Pod
Autoscaler on Minikube and Amazon EKS. The `/cpu` endpoint performs bounded,
side-effect-free work so scale-up and recovery can be measured consistently.

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

## Final-project boundary

The future IoT extension is intentionally absent from the TA1 implementation.
It will start only after the TA1 submission is confirmed and will preserve this
version under the Git tag `ta1-submission`.

## Security

Never commit AWS credentials, kubeconfig files, private keys, certificates, or
raw screenshots that expose account details. The `.gitignore` blocks the most
common secret formats, but every artefact must also be reviewed manually.

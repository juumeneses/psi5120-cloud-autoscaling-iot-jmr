# Deployment and Test Guide

This guide reproduces the PSI5120 TA1 experiments without requiring any IoT
hardware. Commands are intentionally explicit, and generated evidence must not
contain credentials, account secrets, or kubeconfig files.

## 1. Prerequisites

- Docker Desktop with WSL integration;
- Python 3.12 or newer;
- `kubectl` compatible with the cluster;
- Minikube;
- AWS CLI v2 and `eksctl` for the cloud experiment;
- an AWS account authorized to create EKS, EC2, ECR, IAM, and load balancers.

Install and test the application locally:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m pytest -v
docker build -t psi5120-autoscaling-api:1.0.0-ta1 .
```

## 2. Minikube deployment

```bash
minikube start --driver=docker --cpus=4 --memory=6144mb
minikube addons enable metrics-server
minikube image load --overwrite=true psi5120-autoscaling-api:1.0.0-ta1
kubectl apply -k k8s/overlays/minikube
kubectl rollout status deployment/autoscaling-api -n psi5120-ta1
kubectl top pods -n psi5120-ta1
kubectl get hpa -n psi5120-ta1
```

Confirm the API from inside the cluster:

```bash
kubectl run api-smoke --rm -i --restart=Never -n psi5120-ta1 \
  --image=busybox:1.37.0 -- wget -qO- http://autoscaling-api/health
```

Run three independent experiments. Each command records the baseline, five
minutes of load, five minutes of recovery, events, metrics, and the final state.

```bash
bash scripts/run_hpa_experiment.sh minikube 1 300 300
bash scripts/run_hpa_experiment.sh minikube 2 300 300
bash scripts/run_hpa_experiment.sh minikube 3 300 300
```

## 3. EKS deployment

Authenticate the AWS CLI using the course account, verify the identity, and
never save credentials in this repository.

```bash
aws sts get-caller-identity
eksctl create cluster -f eks/cluster.yaml
aws eks update-kubeconfig --name psi5120-ta1-jmr --region us-east-1
```

Run `scripts/eks_build_push.ps1` to create ECR and publish the image. Pass its
printed image URI to `scripts/eks_deploy.ps1`. The practical execution used two
managed `t3.small` nodes because the account's AWS Free Plan rejected
`t3.medium`. Install the managed Metrics Server add-on and validate it:

```bash
aws eks create-addon --cluster-name psi5120-ta1-jmr \
  --addon-name metrics-server --region us-east-1
aws eks wait addon-active --cluster-name psi5120-ta1-jmr \
  --addon-name metrics-server --region us-east-1
kubectl top nodes
```

Execute the same three experiments:

```bash
bash scripts/run_hpa_experiment.sh eks 1 180 240
bash scripts/run_hpa_experiment.sh eks 2 180 240
bash scripts/run_hpa_experiment.sh eks 3 180 240
```

## 4. Required screenshots

For Minikube and EKS, capture the named cluster and nodes, the accessible API,
Metrics Server output, baseline pod/HPA state, scale-up, maximum replicas, and
scale-down. Keep the terminal clock visible where practical. Do not capture AWS
credentials, tokens, kubeconfig contents, or unrelated account information.

## 5. Cleanup

Keep Minikube until its evidence has been checked. For AWS, first validate the
article, screenshots, CSV files, and logs. Only then run:

```powershell
.\scripts\eks_cleanup.ps1
```

Finally confirm in AWS that the EKS cluster, node group, ECR repository, and
load balancer no longer exist.

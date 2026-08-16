# Build once, load the image into Minikube, and apply the local overlay.
$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Image = 'psi5120-autoscaling-api:1.0.0-ta1'

Set-Location $ProjectRoot
docker build --tag $Image .
minikube image load $Image
kubectl apply -k k8s/overlays/minikube
kubectl rollout status deployment/autoscaling-api -n psi5120-ta1 --timeout=180s
kubectl get pods,service,hpa -n psi5120-ta1

# Render an ephemeral overlay with the real ECR URI, then deploy without editing Git files.
param([Parameter(Mandatory)][string]$EcrImage)
$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Template = Join-Path $ProjectRoot 'k8s/overlays/eks/kustomization.yaml'
$RenderedDirectory = Join-Path $env:TEMP 'psi5120-ta1-eks-overlay'

if (Test-Path $RenderedDirectory) {
    Remove-Item -LiteralPath $RenderedDirectory -Recurse -Force
}
New-Item -ItemType Directory -Path $RenderedDirectory | Out-Null
Copy-Item (Join-Path $ProjectRoot 'k8s') (Join-Path $RenderedDirectory 'k8s') -Recurse

$RenderedFile = Join-Path $RenderedDirectory 'k8s/overlays/eks/kustomization.yaml'
(Get-Content $RenderedFile -Raw).Replace('__ECR_IMAGE__', $EcrImage) |
    Set-Content $RenderedFile -Encoding utf8

kubectl apply -k (Split-Path $RenderedFile)
kubectl rollout status deployment/autoscaling-api -n psi5120-ta1 --timeout=300s
kubectl get pods,service,hpa -n psi5120-ta1 -o wide

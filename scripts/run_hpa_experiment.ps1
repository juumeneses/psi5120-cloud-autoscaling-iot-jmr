<#
.SYNOPSIS
Runs one timestamped HPA experiment and stores machine-readable evidence.
.PARAMETER Environment
Evidence group, either minikube or eks.
.PARAMETER Run
Sequential run number; the methodology requires 1, 2, and 3.
.PARAMETER LoadSeconds
Duration of sustained load before recovery observation.
.PARAMETER RecoverySeconds
Duration for observing scale-down after load stops.
#>
param(
    [Parameter(Mandatory)]
    [ValidateSet('minikube', 'eks')]
    [string]$Environment,

    [Parameter(Mandatory)]
    [ValidateRange(1, 3)]
    [int]$Run,

    [ValidateRange(120, 1800)]
    [int]$LoadSeconds = 300,

    [ValidateRange(120, 1800)]
    [int]$RecoverySeconds = 300
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$EvidenceDirectory = Join-Path $ProjectRoot "evidence/raw/$Environment/run-$Run"
$SamplesFile = Join-Path $EvidenceDirectory 'samples.csv'
New-Item -ItemType Directory -Force -Path $EvidenceDirectory | Out-Null

# Capture immutable context before changing the workload.
kubectl config current-context | Out-File (Join-Path $EvidenceDirectory 'context.txt') -Encoding utf8
kubectl get nodes -o wide | Out-File (Join-Path $EvidenceDirectory 'nodes-before.txt') -Encoding utf8
kubectl get all,hpa -n psi5120-ta1 -o wide | Out-File (Join-Path $EvidenceDirectory 'baseline.txt') -Encoding utf8
kubectl top nodes | Out-File (Join-Path $EvidenceDirectory 'top-nodes-before.txt') -Encoding utf8
kubectl top pods -n psi5120-ta1 | Out-File (Join-Path $EvidenceDirectory 'top-pods-before.txt') -Encoding utf8

'timestamp_utc,phase,current_replicas,desired_replicas,cpu_current,cpu_target,pod_count' |
    Out-File $SamplesFile -Encoding utf8

function Add-HpaSample([string]$Phase) {
    $Timestamp = (Get-Date).ToUniversalTime().ToString('o')
    $Current = kubectl get hpa autoscaling-api -n psi5120-ta1 -o jsonpath='{.status.currentReplicas}'
    $Desired = kubectl get hpa autoscaling-api -n psi5120-ta1 -o jsonpath='{.status.desiredReplicas}'
    $CpuCurrent = kubectl get hpa autoscaling-api -n psi5120-ta1 -o jsonpath='{.status.currentMetrics[0].resource.current.averageUtilization}'
    $CpuTarget = kubectl get hpa autoscaling-api -n psi5120-ta1 -o jsonpath='{.spec.metrics[0].resource.target.averageUtilization}'
    $PodCount = kubectl get pods -n psi5120-ta1 -l app.kubernetes.io/name=autoscaling-api --field-selector=status.phase=Running --no-headers 2>$null | Measure-Object | Select-Object -ExpandProperty Count
    "$Timestamp,$Phase,$Current,$Desired,$CpuCurrent,$CpuTarget,$PodCount" |
        Out-File $SamplesFile -Append -Encoding utf8
}

# Recreate the load pod to guarantee a clean start for this run.
kubectl delete pod load-generator -n psi5120-ta1 --ignore-not-found | Out-Null
kubectl apply -f (Join-Path $ProjectRoot 'k8s/load/load-generator.yaml') | Out-Null
$LoadStarted = Get-Date
while (((Get-Date) - $LoadStarted).TotalSeconds -lt $LoadSeconds) {
    Add-HpaSample 'load'
    Start-Sleep -Seconds 15
}

# Removing the source of pressure starts the scale-down observation window.
kubectl delete pod load-generator -n psi5120-ta1 --ignore-not-found | Out-Null
$RecoveryStarted = Get-Date
while (((Get-Date) - $RecoveryStarted).TotalSeconds -lt $RecoverySeconds) {
    Add-HpaSample 'recovery'
    Start-Sleep -Seconds 15
}

kubectl describe hpa autoscaling-api -n psi5120-ta1 | Out-File (Join-Path $EvidenceDirectory 'hpa-describe.txt') -Encoding utf8
kubectl get events -n psi5120-ta1 --sort-by='.lastTimestamp' | Out-File (Join-Path $EvidenceDirectory 'events.txt') -Encoding utf8
kubectl top pods -n psi5120-ta1 | Out-File (Join-Path $EvidenceDirectory 'top-pods-after.txt') -Encoding utf8
kubectl get all,hpa -n psi5120-ta1 -o wide | Out-File (Join-Path $EvidenceDirectory 'final-state.txt') -Encoding utf8

Write-Host "Evidence saved to $EvidenceDirectory"

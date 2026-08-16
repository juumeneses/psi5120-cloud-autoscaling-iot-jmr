#!/usr/bin/env bash
# Run one repeatable HPA experiment from Linux/WSL and capture textual evidence.
set -euo pipefail

environment="${1:?usage: run_hpa_experiment.sh <minikube|eks> <run 1..3> [load_seconds] [recovery_seconds]}"
run_number="${2:?usage: run_hpa_experiment.sh <minikube|eks> <run 1..3> [load_seconds] [recovery_seconds]}"
load_seconds="${3:-300}"
recovery_seconds="${4:-300}"

if [[ ! "$environment" =~ ^(minikube|eks)$ ]] || [[ ! "$run_number" =~ ^[1-3]$ ]]; then
  echo "environment must be minikube or eks; run must be 1, 2, or 3" >&2
  exit 2
fi

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
evidence_dir="$project_root/evidence/raw/$environment/run-$run_number"
samples_file="$evidence_dir/samples.csv"
mkdir -p "$evidence_dir"

# Preserve the cluster identity and baseline before applying load.
kubectl config current-context > "$evidence_dir/context.txt"
kubectl get nodes -o wide > "$evidence_dir/nodes-before.txt"
kubectl get all,hpa -n psi5120-ta1 -o wide > "$evidence_dir/baseline.txt"
kubectl top nodes > "$evidence_dir/top-nodes-before.txt"
kubectl top pods -n psi5120-ta1 > "$evidence_dir/top-pods-before.txt"
printf 'timestamp_utc,phase,current_replicas,desired_replicas,cpu_current,cpu_target,pod_count\n' > "$samples_file"

sample_hpa() {
  local phase="$1"
  local timestamp current desired cpu_current cpu_target pod_count
  timestamp="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  current="$(kubectl get hpa autoscaling-api -n psi5120-ta1 -o jsonpath='{.status.currentReplicas}')"
  desired="$(kubectl get hpa autoscaling-api -n psi5120-ta1 -o jsonpath='{.status.desiredReplicas}')"
  cpu_current="$(kubectl get hpa autoscaling-api -n psi5120-ta1 -o jsonpath='{.status.currentMetrics[0].resource.current.averageUtilization}')"
  cpu_target="$(kubectl get hpa autoscaling-api -n psi5120-ta1 -o jsonpath='{.spec.metrics[0].resource.target.averageUtilization}')"
  pod_count="$(kubectl get pods -n psi5120-ta1 -l app.kubernetes.io/name=autoscaling-api --field-selector=status.phase=Running --no-headers | wc -l)"
  printf '%s,%s,%s,%s,%s,%s,%s\n' "$timestamp" "$phase" "$current" "$desired" "$cpu_current" "$cpu_target" "$pod_count" | tee -a "$samples_file"
}

# Recreating the pod produces an unambiguous load start for every run.
kubectl delete pod load-generator -n psi5120-ta1 --ignore-not-found >/dev/null
kubectl apply -f "$project_root/k8s/load/load-generator.yaml" >/dev/null
load_started="$(date +%s)"
while (( $(date +%s) - load_started < load_seconds )); do
  sample_hpa load
  sleep 15
done

# Removing the producer begins the recovery and scale-down interval.
kubectl delete pod load-generator -n psi5120-ta1 --ignore-not-found >/dev/null
recovery_started="$(date +%s)"
while (( $(date +%s) - recovery_started < recovery_seconds )); do
  sample_hpa recovery
  sleep 15
done

kubectl describe hpa autoscaling-api -n psi5120-ta1 > "$evidence_dir/hpa-describe.txt"
kubectl get events -n psi5120-ta1 --sort-by='.lastTimestamp' > "$evidence_dir/events.txt"
kubectl top pods -n psi5120-ta1 > "$evidence_dir/top-pods-after.txt"
kubectl get all,hpa -n psi5120-ta1 -o wide > "$evidence_dir/final-state.txt"
echo "evidence_saved=$evidence_dir"

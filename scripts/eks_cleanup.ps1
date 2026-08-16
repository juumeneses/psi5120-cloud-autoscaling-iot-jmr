# Delete billable resources only after evidence and PDF validation are complete.
$ErrorActionPreference = 'Stop'
$Region = 'us-east-1'
$Cluster = 'psi5120-ta1-jmr'
$Repository = 'psi5120-ta1-jmr-autoscaling-api'

# Deleting the Service first gives AWS time to remove its external load balancer.
kubectl delete namespace psi5120-ta1 --ignore-not-found
eksctl delete cluster --name $Cluster --region $Region --wait
aws ecr delete-repository --repository-name $Repository --region $Region --force

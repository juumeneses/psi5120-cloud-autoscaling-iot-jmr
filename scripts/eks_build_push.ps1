# Build the image, create/reuse ECR, authenticate Docker, and publish one fixed tag.
$ErrorActionPreference = 'Stop'
$Region = 'us-east-1'
$Repository = 'psi5120-ta1-jmr-autoscaling-api'
$Tag = '1.0.0-ta1'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

$AccountId = aws sts get-caller-identity --query Account --output text
$Registry = "$AccountId.dkr.ecr.$Region.amazonaws.com"
$Image = "$Registry/${Repository}:$Tag"

aws ecr describe-repositories --repository-names $Repository --region $Region 2>$null
if ($LASTEXITCODE -ne 0) {
    aws ecr create-repository --repository-name $Repository --region $Region --image-scanning-configuration scanOnPush=true | Out-Null
}

aws ecr get-login-password --region $Region | docker login --username AWS --password-stdin $Registry
docker build --tag $Image .
docker push $Image
Write-Output $Image

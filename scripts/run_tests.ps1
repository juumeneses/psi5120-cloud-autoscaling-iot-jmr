# Run the deterministic local test suite with the selected Python interpreter.
$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot
python -m pytest -v

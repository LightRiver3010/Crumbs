[CmdletBinding()]
param(
    [string]$OutputPath = (Join-Path $PSScriptRoot "bundle")
)

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
if (Test-Path $OutputPath) {
    throw "Output path already exists. Choose a new path or remove the staging bundle first."
}

$dagsRoot = Join-Path $OutputPath "dags"
$projectRoot = Join-Path $dagsRoot "project"
$dbtRoot = Join-Path $projectRoot "dbt"
New-Item -ItemType Directory -Path $projectRoot, $dbtRoot -Force | Out-Null

Copy-Item (Join-Path $repoRoot "airflow\dags\menu_ingestion.py") $dagsRoot
foreach ($directory in @("menu_ingestion", "shared", "config", "sql")) {
    Copy-Item (Join-Path $repoRoot $directory) $projectRoot -Recurse
}

foreach ($file in @("dbt_project.yml", "profiles.yml")) {
    Copy-Item (Join-Path $repoRoot "dbt\$file") $dbtRoot
}
foreach ($directory in @("models", "tests", "macros", "seeds")) {
    $source = Join-Path $repoRoot "dbt\$directory"
    if (Test-Path $source) {
        Copy-Item $source $dbtRoot -Recurse
    }
}

Get-ChildItem -Path $OutputPath -Directory -Filter "__pycache__" -Recurse |
    Remove-Item -Recurse -Force
Get-ChildItem -Path $OutputPath -File -Include "*.pyc", "*.pyo" -Recurse |
    Remove-Item -Force

Write-Output "Composer DAG bundle staged at $OutputPath"

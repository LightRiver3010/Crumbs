[CmdletBinding()]
param([string]$OutputPath = (Join-Path $PSScriptRoot "bundle"))
$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "../..")).Path
if (Test-Path -LiteralPath $OutputPath) { throw "Output path already exists; choose a new staging directory." }
$bundleRoot = [System.IO.Path]::GetFullPath($OutputPath)
$dagsRoot = Join-Path $bundleRoot "dags"
$projectRoot = Join-Path $dagsRoot "project"
New-Item -ItemType Directory -Path $projectRoot -Force | Out-Null
Copy-Item -LiteralPath (Join-Path $repoRoot "airflow/dags/menu_ingestion.py") -Destination $dagsRoot
# Explicit file types only: never copy .env, credentials, caches, or build artifacts.
foreach ($directory in @("menu_ingestion", "shared", "config", "sql")) {
    $sourceRoot = Join-Path $repoRoot $directory
    Get-ChildItem -LiteralPath $sourceRoot -File -Recurse | Where-Object {
        $_.Extension -in @(".py", ".json", ".sql") -and $_.FullName -notmatch "[\\/]__pycache__[\\/]"
    } | ForEach-Object {
        $relative = [System.IO.Path]::GetRelativePath($repoRoot, $_.FullName)
        $destination = Join-Path $projectRoot $relative
        New-Item -ItemType Directory -Path (Split-Path $destination) -Force | Out-Null
        Copy-Item -LiteralPath $_.FullName -Destination $destination
    }
}
$dbtRoot = Join-Path $projectRoot "dbt"
New-Item -ItemType Directory -Path $dbtRoot -Force | Out-Null
foreach ($file in @("dbt_project.yml", "profiles.yml")) {
    Copy-Item -LiteralPath (Join-Path $repoRoot "dbt/$file") -Destination $dbtRoot
}
foreach ($directory in @("models", "tests", "macros", "seeds")) {
    $sourceRoot = Join-Path $repoRoot "dbt/$directory"
    if (Test-Path -LiteralPath $sourceRoot) {
        Get-ChildItem -LiteralPath $sourceRoot -File -Recurse | Where-Object {
            $_.Extension -in @(".sql", ".yml", ".yaml", ".csv")
        } | ForEach-Object {
            $relative = [System.IO.Path]::GetRelativePath((Join-Path $repoRoot "dbt"), $_.FullName)
            $destination = Join-Path $dbtRoot $relative
            New-Item -ItemType Directory -Path (Split-Path $destination) -Force | Out-Null
            Copy-Item -LiteralPath $_.FullName -Destination $destination
        }
    }
}
# Airflow 2 uses regex ignore syntax by default; project files remain importable.
Set-Content -LiteralPath (Join-Path $projectRoot ".airflowignore") -Value ".*" -Encoding utf8
Write-Output "Composer DAG bundle staged at $bundleRoot"

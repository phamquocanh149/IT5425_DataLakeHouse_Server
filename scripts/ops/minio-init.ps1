<#
.SYNOPSIS
    Windows wrapper for scripts/ops/minio-init.sh.

.DESCRIPTION
    scripts/ops/minio-init.sh is not executed on the host. Compose mounts it
    read-only into the Linux `mc` (MinIO client) container and runs it with
    /bin/sh, so no native port is needed. This script (re)runs the same
    provisioning from PowerShell by delegating to Docker Compose.

    Requires Docker Desktop with Linux containers and Docker Compose v2.

.EXAMPLE
    scripts\ops\minio-init.ps1
#>
[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Push-Location $root
try {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        throw 'Docker is required (Docker Desktop with Linux containers).'
    }
    docker compose version *> $null
    if ($LASTEXITCODE -ne 0) {
        throw 'Docker Compose v2 is required.'
    }
    if (-not (Test-Path (Join-Path $root '.env')) -and (Test-Path (Join-Path $root '.env.example'))) {
        Write-Warning 'No .env found. Copy .env.example to .env and set MINIO_ROOT_USER, MINIO_ROOT_PASSWORD, S3_ACCESS_KEY, S3_SECRET_KEY and MEDALLION_S3_SECRET_KEY.'
    }
    Write-Host '[minio-init] Running: docker compose run --rm minio-init'
    docker compose run --rm minio-init
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}
finally {
    Pop-Location
}

@echo off
rem ---------------------------------------------------------------------------
rem Windows wrapper for scripts/ops/minio-init.sh.
rem
rem The .sh file is NOT run on the host: Compose mounts it read-only into the
rem Linux `mc` (MinIO client) container and runs it with /bin/sh. That is why a
rem native port is not needed. This wrapper (re)runs the same provisioning from
rem Windows by delegating to Docker Compose, so it also works with Docker
rem Desktop on Windows and with Git Bash without MSYS path conversion issues.
rem
rem Usage (from anywhere):
rem     scripts\ops\minio-init.bat
rem
rem Requires: Docker Desktop with Linux containers and Docker Compose v2.
rem ---------------------------------------------------------------------------
setlocal enableextensions

rem %~dp0 ends with a backslash; go up two levels to the repository root.
set "ROOT=%~dp0..\.."
pushd "%ROOT%" >nul 2>nul
if errorlevel 1 (
    echo [minio-init] Cannot enter repository root: %ROOT% 1>&2
    endlocal
    exit /b 1
)

where docker >nul 2>nul
if errorlevel 1 (
    echo [minio-init] Docker is required ^(Docker Desktop with Linux containers^). 1>&2
    popd
    endlocal
    exit /b 1
)

docker compose version >nul 2>nul
if errorlevel 1 (
    echo [minio-init] Docker Compose v2 is required. Run: docker compose version 1>&2
    popd
    endlocal
    exit /b 1
)

if not exist ".env" if exist ".env.example" (
    echo [minio-init] No .env found. Copy .env.example to .env and set MINIO_ROOT_USER, 1>&2
    echo [minio-init] MINIO_ROOT_PASSWORD, S3_ACCESS_KEY, S3_SECRET_KEY and MEDALLION_S3_SECRET_KEY. 1>&2
)

echo [minio-init] Running: docker compose run --rm minio-init
docker compose run --rm minio-init
set "CODE=%ERRORLEVEL%"

popd
endlocal & exit /b %CODE%

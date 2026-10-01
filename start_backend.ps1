# Starts the Digital Tailor API (http://127.0.0.1:5000) with the project's OWN Python environment, backend\venv,
# so it always runs with the package versions in backend\requirements.txt - not whatever Python is on the PATH.
#
#   powershell -ExecutionPolicy Bypass -File start_backend.ps1
#
# First run: creates backend\venv, installs the requirements (a few minutes, needs the internet) and creates
# backend\.env with two random secret keys if the file does not exist. Later runs start at once.
# MongoDB must be running on localhost:27017. Stop the server with Ctrl+C.

$ErrorActionPreference = "Stop"
$backend = Join-Path $PSScriptRoot "backend"
$python = Join-Path $backend "venv\Scripts\python.exe"

if (-not (Test-Path $python)) {
    Write-Host "Creating the Python environment in backend\venv ..."
    $base = Get-Command py -ErrorAction SilentlyContinue
    if ($base) { & py -3 -m venv (Join-Path $backend "venv") } else { & python -m venv (Join-Path $backend "venv") }
    if (-not (Test-Path $python)) { throw "Python 3.10 or newer is needed (https://www.python.org/downloads/)." }
}

# the packages the server needs; installed only when one is missing
& $python -c "import flask, flask_cors, flask_jwt_extended, bcrypt, mongoengine, reportlab, PIL, numpy, torch, ultralytics" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Installing the backend requirements (first run only) ..."
    & $python -m pip install --upgrade pip
    & $python -m pip install -r (Join-Path $backend "requirements.txt")
    if ($LASTEXITCODE -ne 0) { throw "The requirements could not be installed. See the messages above." }
}

$envFile = Join-Path $backend ".env"
if (-not (Test-Path $envFile)) {
    Write-Host "Creating backend\.env with new random secret keys ..."
    $key1 = & $python -c "import secrets; print(secrets.token_hex(32))"
    $key2 = & $python -c "import secrets; print(secrets.token_hex(32))"
    $text = (Get-Content (Join-Path $backend ".env.example") -Raw) -replace "(?m)^SECRET_KEY=\s*$", "SECRET_KEY=$key1" -replace "(?m)^JWT_SECRET_KEY=\s*$", "JWT_SECRET_KEY=$key2"
    [System.IO.File]::WriteAllText($envFile, $text, (New-Object System.Text.UTF8Encoding($false)))
}

Set-Location $backend
& $python run.py

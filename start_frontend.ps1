# Starts the Digital Tailor web app (http://localhost:3000). The API must be running too (start_backend.ps1).
#
#   powershell -ExecutionPolicy Bypass -File start_frontend.ps1
#
# First run: installs the JavaScript packages (needs the internet). Stop with Ctrl+C.

$ErrorActionPreference = "Stop"
$frontend = Join-Path $PSScriptRoot "frontend"
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) { throw "Node.js 18 or newer is needed (https://nodejs.org/)." }

Set-Location $frontend
if (-not (Test-Path (Join-Path $frontend "node_modules"))) {
    Write-Host "Installing the frontend packages (first run only) ..."
    npm install
    if ($LASTEXITCODE -ne 0) { throw "npm install failed. See the messages above." }
}
npm run dev

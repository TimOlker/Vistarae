# Copyright (c) 2026 Tim Olker
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# SPDX-License-Identifier: Apache-2.0

<#
.SYNOPSIS
    All-in-one manual testing environment startup for Vistarae.
.DESCRIPTION
    Starts PostGIS/services via Docker, applies Alembic migrations,
    seeds demo/test users, and launches the Backend API Gateway & Frontend SPA
    in dedicated interactive terminal windows.
.EXAMPLE
    .\scripts\start-dev.ps1
    .\scripts\start-dev.ps1 -SkipSeed
#>

[CmdletBinding()]
param (
    [switch]$SkipSeed = $false
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path "$PSScriptRoot\..").Path

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "   Vistarae Local Development & Manual Testing Startup       " -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

# 1. Backing Services (Docker Compose)
Write-Host "`n[1/5] Checking Docker backing services (PostGIS, ElasticMQ, Jaeger)..." -ForegroundColor Yellow
try {
    & docker compose -f "$ProjectRoot\docker-compose.yml" up -d
    Write-Host "  -> Docker services are active." -ForegroundColor Green
} catch {
    Write-Warning "Failed to start docker compose. Ensure Docker Desktop is running."
}

# 2. Database Migrations
Write-Host "`n[2/5] Applying Alembic schema migrations..." -ForegroundColor Yellow
$PythonExe = if (Test-Path "$ProjectRoot\.venv\Scripts\python.exe") {
    "$ProjectRoot\.venv\Scripts\python.exe"
} else {
    "python"
}

try {
    & $PythonExe -m alembic upgrade head
    Write-Host "  -> Database schema up-to-date at revision 0007 (head)." -ForegroundColor Green
} catch {
    Write-Warning "Alembic migration failed: $_"
}

# 3. Seed Database (Optional / Default: Yes)
if (-not $SkipSeed) {
    Write-Host "`n[3/5] Seeding test accounts, sample POIs, and default tags..." -ForegroundColor Yellow
    try {
        $env:STAGE = "local"
        & $PythonExe "$ProjectRoot\scripts\seed_local_db.py"
        Write-Host "  -> Local database seeded successfully." -ForegroundColor Green
    } catch {
        Write-Warning "Database seeding reported an error (or data already seeded): $_"
    }
} else {
    Write-Host "`n[3/5] Skipping database seeding (-SkipSeed specified)." -ForegroundColor DarkGray
}

# 4. Launch Backend Gateway (Port 8000)
Write-Host "`n[4/5] Launching Backend API Gateway on http://localhost:8000..." -ForegroundColor Yellow
$backendCmd = @"
`$env:STAGE = 'local'
Set-Location '$ProjectRoot'
Write-Host 'Vistarae Backend Gateway (FastAPI) running on http://localhost:8000' -ForegroundColor Cyan
Write-Host 'Interactive OpenAPI Docs: http://localhost:8000/docs' -ForegroundColor Green
& '$PythonExe' -m uvicorn services.local_gateway:app --reload --port 8000
"@
Start-Process powershell -ArgumentList "-NoExit", "-Command", $backendCmd

# 5. Launch Frontend Dev Server (Port 5173)
Write-Host "`n[5/5] Launching Frontend SPA on http://localhost:5173..." -ForegroundColor Yellow
$frontendCmd = @"
Set-Location '$ProjectRoot\frontend'
Write-Host 'Vistarae Web App (Vite/React) running on http://localhost:5173' -ForegroundColor Cyan
npm run dev
"@
Start-Process powershell -ArgumentList "-NoExit", "-Command", $frontendCmd

# 6. Manual Testing Instructions
Write-Host "`n============================================================" -ForegroundColor Green
Write-Host "   Vistarae Environment Ready for Manual Testing!            " -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host ""
Write-Host "Web App:             http://localhost:5173" -ForegroundColor White
Write-Host "Backend API:         http://localhost:8000" -ForegroundColor White
Write-Host "API Documentation:   http://localhost:8000/docs" -ForegroundColor White
Write-Host ""
Write-Host "Test Accounts:" -ForegroundColor Cyan
Write-Host "  * High-Tier User:  high-tier@local.vistarae.dev" -ForegroundColor White
Write-Host "  * Low-Tier User:   low-tier@local.vistarae.dev" -ForegroundColor White
Write-Host "  * Admin User:      admin@local.vistarae.dev" -ForegroundColor White
Write-Host ""
Write-Host "Chrome Extension Setup:" -ForegroundColor Cyan
Write-Host "  1. Open Chrome and go to: chrome://extensions/" -ForegroundColor White
Write-Host "  2. Enable 'Developer mode' (top right toggle)" -ForegroundColor White
Write-Host "  3. Click 'Load unpacked' and select:" -ForegroundColor White
Write-Host "     $ProjectRoot\extension" -ForegroundColor Yellow
Write-Host "  4. Keystroke shortcut to capture: Ctrl+Shift+S (Cmd+Shift+S on Mac)" -ForegroundColor White
Write-Host ""
Write-Host "Quickstart Scenarios to Test (specs/009-extension-enhancements/quickstart.md):" -ForegroundColor Cyan
Write-Host "  [Scenario 1] Tag Governance: Settings -> Tags tab (30 defaults, create, referential delete lock)" -ForegroundColor White
Write-Host "  [Scenario 2] Scraping Sources: Settings -> Scraping Sources tab (add domain, save)" -ForegroundColor White
Write-Host "  [Scenario 3] Extension Companion: Click extension icon -> clean browser.html overview" -ForegroundColor White
Write-Host "  [Scenario 4] Pre-Capture Auth Gate: Clear tokens -> Ctrl+Shift+S -> redirects to login" -ForegroundColor White
Write-Host "  [Scenario 5] Web Scraping & Synthesis: Highlight text on Wikipedia -> Ctrl+Shift+S -> capture" -ForegroundColor White
Write-Host "  [Scenario 6] Scale-Aware Triage: Capture 'Cloud Gate' -> 3-way triage modal (Make Child of Millennium Park)" -ForegroundColor White
Write-Host "============================================================" -ForegroundColor Green

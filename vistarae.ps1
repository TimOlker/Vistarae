<#
.SYNOPSIS
    Vistarae Windows PowerShell Developer Helper (powered by uv)

.EXAMPLE
    .\vistarae.ps1 sync
    .\vistarae.ps1 up
    .\vistarae.ps1 down
    .\vistarae.ps1 migrate
    .\vistarae.ps1 seed
    .\vistarae.ps1 test
    .\vistarae.ps1 lint
    .\vistarae.ps1 run
#>

param (
    [Parameter(Position=0, Mandatory=$false)]
    [ValidateSet("sync", "up", "down", "restart", "logs", "migrate", "seed", "clean-db", "reset-db", "test", "lint", "run", "scrape", "register-protocol", "unregister-protocol", "help")]
    [string]$Command = "help",
    [Parameter(Position=1, Mandatory=$false)]
    [string]$PhotoDir = "",
    [switch]$CacheFolders,
    [switch]$RescanFolders
)

function Invoke-PythonTool {
    param (
        [string]$ToolName,
        [string[]]$ToolArgs = @()
    )
    if (Get-Command uv -ErrorAction SilentlyContinue) {
        & uv run $ToolName @ToolArgs
    } elseif (Test-Path ".\.venv\Scripts\$ToolName.exe") {
        & ".\.venv\Scripts\$ToolName.exe" @ToolArgs
    } else {
        & python -m $ToolName @ToolArgs
    }
}

function Invoke-PythonScript {
    param (
        [string]$ScriptPath,
        [string[]]$ScriptArgs = @()
    )
    if (Get-Command uv -ErrorAction SilentlyContinue) {
        & uv run python $ScriptPath @ScriptArgs
    } elseif (Test-Path ".\.venv\Scripts\python.exe") {
        & ".\.venv\Scripts\python.exe" $ScriptPath @ScriptArgs
    } else {
        & python $ScriptPath @ScriptArgs
    }
}

switch ($Command) {
    "sync" {
        Write-Host "Syncing workspace dependencies with uv..." -ForegroundColor Cyan
        if (Get-Command uv -ErrorAction SilentlyContinue) {
            & uv sync
        } else {
            & python -m pip install -e . -e ./packages/core
        }
        Write-Host "Sync complete." -ForegroundColor Green
    }
    "up" {
        Write-Host "Starting Vistarae services (PostGIS, Jaeger, ElasticMQ)..." -ForegroundColor Cyan
        docker compose up -d
    }
    "down" {
        Write-Host "Stopping Vistarae services..." -ForegroundColor Cyan
        docker compose down
    }
    "restart" {
        Write-Host "Restarting Vistarae services..." -ForegroundColor Cyan
        docker compose restart
    }
    "logs" {
        Write-Host "Tailing service logs..." -ForegroundColor Cyan
        docker compose logs -f
    }
    "migrate" {
        Write-Host "Applying Alembic schema migrations..." -ForegroundColor Cyan
        Invoke-PythonTool "alembic" @("upgrade", "head")
        Write-Host "Migrations completed." -ForegroundColor Green
    }
    "seed" {
        Write-Host "Loading seed data into local database..." -ForegroundColor Cyan
        Invoke-PythonScript "scripts/seed_local_db.py"
        Write-Host "Seed completed." -ForegroundColor Green
    }
    "clean-db" {
        Write-Host "Clearing database tables (preserving schema)..." -ForegroundColor Yellow
        docker exec -i vistarae-db psql -U postgres -d vistarae -c "TRUNCATE pois, poi_access_points, poi_list_memberships, lists, user_tags, idempotency_keys, user_quotas, user_metrics, user_preferences, users CASCADE;"
        Write-Host "Database cleared." -ForegroundColor Green
    }
    "reset-db" {
        Write-Host "Completely resetting database schema and re-migrating..." -ForegroundColor Red
        docker exec -i vistarae-db psql -U postgres -d vistarae -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
        & $PSCommandPath migrate
        Write-Host "Database completely reset and migrated." -ForegroundColor Green
    }
    "test" {
        Write-Host "Running pytest suite with coverage..." -ForegroundColor Cyan
        Invoke-PythonTool "pytest" @("-v")
    }
    "lint" {
        Write-Host "Running ruff linter..." -ForegroundColor Cyan
        Invoke-PythonTool "ruff" @("check", ".")
    }
    "run" {
        Write-Host "Starting Vistarae local gateway on http://localhost:8030..." -ForegroundColor Cyan
        $env:STAGE = "local"
        Invoke-PythonTool "uvicorn" @("services.local_gateway:app", "--reload", "--port", "8030")
    }
    "scrape" {
        Write-Host "Running Vistarae Photo Scraper..." -ForegroundColor Cyan
        $argsList = @()
        if ($PhotoDir -ne "") { $argsList += @("--dir", $PhotoDir) }
        if ($CacheFolders) { $argsList += "--cache-folders" }
        if ($RescanFolders) { $argsList += "--rescan-folders" }
        Invoke-PythonScript "photo_scraper/main.py" $argsList
    }
    "register-protocol" {
        & "$PSScriptRoot\scripts\register_protocol.ps1"
    }
    "unregister-protocol" {
        & "$PSScriptRoot\scripts\unregister_protocol.ps1"
    }
    Default {
        Write-Host "Vistarae Windows Developer Helper (powered by uv):" -ForegroundColor Yellow
        Write-Host "  .\vistarae.ps1 sync                - Sync dependencies and editable packages with uv"
        Write-Host "  .\vistarae.ps1 up                  - Start PostGIS, Jaeger, and background services"
        Write-Host "  .\vistarae.ps1 down                - Stop all running services"
        Write-Host "  .\vistarae.ps1 restart             - Restart all services"
        Write-Host "  .\vistarae.ps1 logs                - Tail logs across services"
        Write-Host "  .\vistarae.ps1 migrate             - Execute Alembic migrations against active database"
        Write-Host "  .\vistarae.ps1 seed                - Seed local database with test users"
        Write-Host "  .\vistarae.ps1 clean-db            - Clear database tables (keeps schema)"
        Write-Host "  .\vistarae.ps1 reset-db            - Wipe schema and re-run all migrations from scratch"
        Write-Host "  .\vistarae.ps1 test                - Run pytest suite with coverage"
        Write-Host "  .\vistarae.ps1 lint                - Run ruff code quality checks"
        Write-Host "  .\vistarae.ps1 run                 - Start local development gateway"
        Write-Host "  .\vistarae.ps1 scrape              - Run photo scraper tool (optional: [PhotoDir])"
        Write-Host "  .\vistarae.ps1 register-protocol   - Register vistarae-folder:// protocol in Windows HKCU"
        Write-Host "  .\vistarae.ps1 unregister-protocol - Unregister vistarae-folder:// protocol from Windows"
    }
}


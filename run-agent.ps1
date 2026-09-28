$ErrorActionPreference = "Stop"

if (-not (Test-Path ".venv")) {
    py -3.12 -m venv .venv
}

& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\pip.exe install -e .
& .\.venv\Scripts\python.exe -m playwright install chromium

Write-Host ""
Write-Host "Starting local command agent..."
Write-Host "Watching commands\current.json"
Write-Host ""

& .\.venv\Scripts\python.exe -m browser_mcp.command_agent

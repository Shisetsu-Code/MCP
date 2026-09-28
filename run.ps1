$ErrorActionPreference = "Stop"

if (-not (Test-Path ".venv")) {
    py -3.12 -m venv .venv
}

& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\pip.exe install -e .
& .\.venv\Scripts\python.exe -m playwright install chromium

$env:MCP_HOST = "127.0.0.1"
$env:MCP_PORT = "8765"

Write-Host ""
Write-Host "Shisetsu Browser MCP"
Write-Host "MCP endpoint: http://127.0.0.1:8765/mcp"
Write-Host ""
Write-Host "For an existing Chrome, start Chrome with remote debugging on 9222."
Write-Host "Otherwise browser_start can launch Chromium itself."
Write-Host ""

& .\.venv\Scripts\python.exe -m browser_mcp.server

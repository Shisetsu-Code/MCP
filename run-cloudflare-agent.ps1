$ErrorActionPreference = "Stop"

if (-not $env:CF_CONTROL_URL) {
    throw "Set CF_CONTROL_URL, for example https://shisetsu-browser-control.<subdomain>.workers.dev"
}
if (-not $env:CF_CONTROL_TOKEN) {
    throw "Set CF_CONTROL_TOKEN to the same secret configured in Cloudflare."
}

if (-not (Test-Path ".venv")) {
    py -3.12 -m venv .venv
}

& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\pip.exe install -e .
& .\.venv\Scripts\python.exe -m playwright install chromium

if (-not $env:CF_AGENT_ID) {
    $env:CF_AGENT_ID = "main"
}

Write-Host ""
Write-Host "Starting Cloudflare WSS browser agent"
Write-Host "Control URL: $env:CF_CONTROL_URL"
Write-Host "Agent ID: $env:CF_AGENT_ID"
Write-Host ""

& .\.venv\Scripts\python.exe -m browser_mcp.cloudflare_agent

$chromeCandidates = @(
    "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
    "$env:ProgramFiles(x86)\Google\Chrome\Application\chrome.exe",
    "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe"
)

$chrome = $chromeCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $chrome) {
    throw "Google Chrome not found."
}

$profile = Join-Path $PSScriptRoot ".chrome-profile"
New-Item -ItemType Directory -Force -Path $profile | Out-Null

Start-Process $chrome -ArgumentList @(
    "--remote-debugging-port=9222",
    "--remote-debugging-address=127.0.0.1",
    "--user-data-dir=$profile"
)

Write-Host "Chrome started with CDP at http://127.0.0.1:9222"

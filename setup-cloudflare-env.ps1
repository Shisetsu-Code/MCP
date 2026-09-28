$ErrorActionPreference = "Stop"

$defaultUrl = "https://shisetsu-browser-control.braian-n-l.workers.dev"

$url = Read-Host "CF_CONTROL_URL [$defaultUrl]"
if ([string]::IsNullOrWhiteSpace($url)) {
    $url = $defaultUrl
}

$token = Read-Host "CF_CONTROL_TOKEN"
if ([string]::IsNullOrWhiteSpace($token)) {
    throw "Token cannot be empty."
}

$agentId = Read-Host "CF_AGENT_ID [main]"
if ([string]::IsNullOrWhiteSpace($agentId)) {
    $agentId = "main"
}

[Environment]::SetEnvironmentVariable("CF_CONTROL_URL", $url, "User")
[Environment]::SetEnvironmentVariable("CF_CONTROL_TOKEN", $token, "User")
[Environment]::SetEnvironmentVariable("CF_AGENT_ID", $agentId, "User")

$env:CF_CONTROL_URL = $url
$env:CF_CONTROL_TOKEN = $token
$env:CF_AGENT_ID = $agentId

Write-Host ""
Write-Host "Cloudflare control environment saved for this Windows user."
Write-Host "CF_CONTROL_URL=$url"
Write-Host "CF_AGENT_ID=$agentId"
Write-Host "Token saved without printing it."

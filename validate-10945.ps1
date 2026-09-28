$ErrorActionPreference = "Stop"

if (-not $env:CF_CONTROL_URL) {
    $env:CF_CONTROL_URL = [Environment]::GetEnvironmentVariable("CF_CONTROL_URL", "User")
}
if (-not $env:CF_CONTROL_TOKEN) {
    $env:CF_CONTROL_TOKEN = [Environment]::GetEnvironmentVariable("CF_CONTROL_TOKEN", "User")
}
if (-not $env:CF_AGENT_ID) {
    $env:CF_AGENT_ID = [Environment]::GetEnvironmentVariable("CF_AGENT_ID", "User")
}

if (-not $env:CF_CONTROL_URL) {
    throw "CF_CONTROL_URL is not set. Run .\setup-cloudflare-env.ps1 once."
}
if (-not $env:CF_CONTROL_TOKEN) {
    throw "CF_CONTROL_TOKEN is not set. Run .\setup-cloudflare-env.ps1 once."
}
if (-not $env:CF_AGENT_ID) {
    $env:CF_AGENT_ID = "main"
}

$runtime = "https://staticdemo.yggdrasilgaming.com/10945/index.html?appsrv=https://demo.yggdrasilgaming.com&boostUrl=/boost/current/boost.js&channel=pc&countryCode=ar&currency=EUR&fullscreen=yes&gameid=10945&key=&lang=en&license=mt&org=Demo&pcUrl=/partnerconnect/current/partnerconnect.js"

$steps = @(
    # RANDOM BANK
    @{ action = "browser_open"; args = @{ url = $runtime } },
    @{ action = "browser_wait"; args = @{ milliseconds = 7000 } },
    @{ action = "browser_click_relative"; args = @{ rx = 0.5028; ry = 0.786 } },
    @{ action = "browser_wait"; args = @{ milliseconds = 1800 } },
    @{ action = "browser_click_relative"; args = @{ rx = 0.9479; ry = 0.801 } },
    @{ action = "network_clear"; args = @{} },
    @{ action = "browser_click_relative"; args = @{ rx = 0.7965; ry = 0.578 } },
    @{ action = "browser_wait"; args = @{ milliseconds = 300 } },
    @{ action = "browser_click_relative"; args = @{ rx = 0.5424; ry = 0.540 } },
    @{ action = "network_wait"; args = @{ contains = "fn=play"; timeout_ms = 10000 } },

    # ALL BANKS
    @{ action = "browser_open"; args = @{ url = $runtime } },
    @{ action = "browser_wait"; args = @{ milliseconds = 7000 } },
    @{ action = "browser_click_relative"; args = @{ rx = 0.5028; ry = 0.786 } },
    @{ action = "browser_wait"; args = @{ milliseconds = 1800 } },
    @{ action = "browser_click_relative"; args = @{ rx = 0.9479; ry = 0.801 } },
    @{ action = "network_clear"; args = @{} },
    @{ action = "browser_click_relative"; args = @{ rx = 0.3979; ry = 0.781 } },
    @{ action = "browser_wait"; args = @{ milliseconds = 300 } },
    @{ action = "browser_click_relative"; args = @{ rx = 0.5424; ry = 0.540 } },
    @{ action = "network_wait"; args = @{ contains = "fn=play"; timeout_ms = 10000 } }
)

$tmp = Join-Path $env:TEMP "validate-10945-random-all.json"

@{ steps = $steps } |
    ConvertTo-Json -Depth 20 |
    Set-Content -Path $tmp -Encoding UTF8

$id = "validate-10945-random-all-" + [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()

Write-Host "Sending sequence: $id"

py -3.12 .\cloudflare_client.py send sequence --id $id --args-file $tmp

Write-Host ""
Write-Host "Waiting for completion..."

for ($i = 0; $i -lt 60; $i++) {
    Start-Sleep -Milliseconds 500
    $raw = py -3.12 .\cloudflare_client.py get $id
    $obj = $raw | ConvertFrom-Json
    if ($obj.command.status -in @("done", "error")) {
        $raw
        exit 0
    }
}

throw "Timed out waiting for $id"

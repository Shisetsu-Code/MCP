# Cloudflare realtime control plane

This directory replaces GitHub as the interactive transport between ChatGPT/control clients and the local browser agent.

Architecture:

```
control client
  -> HTTPS API
Cloudflare Worker
  -> Durable Object
  <-> persistent WSS
local Windows agent
  -> Playwright/CDP
  -> Chrome

D1 stores:
- commands
- command results
- events
- current agent state

R2 stores:
- screenshots

GitHub remains only for final versioned evidence.
```

## Deploy

From the repository root:

```powershell
cd cloudflare
npm install
npx wrangler login
```

Create D1 and let Wrangler add the binding to `wrangler.jsonc`:

```powershell
npx wrangler d1 create shisetsu-browser-control --binding DB --update-config
```

Create R2 and add the binding:

```powershell
npx wrangler r2 bucket create shisetsu-browser-screenshots --binding SCREENSHOTS --update-config
```

Apply the D1 schema remotely:

```powershell
npx wrangler d1 execute DB --remote --file=./schema.sql
```

Generate a control token:

```powershell
py -3.12 -c "import secrets; print(secrets.token_urlsafe(32))"
```

Copy that value, then set the Worker secret:

```powershell
npx wrangler secret put CONTROL_TOKEN
```

Deploy:

```powershell
npx wrangler deploy
```

Wrangler prints a URL similar to:

```
https://shisetsu-browser-control.<your-subdomain>.workers.dev
```

Keep the control token private.

## Run the Windows agent

Back in the repository root:

```powershell
git pull
.\start-chrome.ps1
```

Then in another PowerShell:

```powershell
$env:CF_CONTROL_URL="https://shisetsu-browser-control.<your-subdomain>.workers.dev"
$env:CF_CONTROL_TOKEN="<same CONTROL_TOKEN>"
$env:CF_AGENT_ID="main"

.\run-cloudflare-agent.ps1
```

The agent keeps one WSS connection open and automatically reconnects.

## API

All API endpoints except `/health` require:

```
X-Control-Token: <CONTROL_TOKEN>
```

### Send a command

```http
POST /api/command
Content-Type: application/json
X-Control-Token: ...
```

Example body:

```json
{
  "id": "buy-test-1",
  "agent_id": "main",
  "action": "sequence",
  "args": {
    "steps": [
      {
        "action": "network_clear",
        "args": {}
      },
      {
        "action": "browser_click_relative",
        "args": {"rx": 0.8, "ry": 0.58}
      },
      {
        "action": "browser_click_relative",
        "args": {"rx": 0.55, "ry": 0.54}
      },
      {
        "action": "network_wait",
        "args": {
          "contains": "fn=play",
          "timeout_ms": 10000
        }
      }
    ]
  }
}
```

### Read a command/result

```
GET /api/command/<id>
```

Statuses:

```
pending
sent
running
done
error
```

### Read events

```
GET /api/events?agent_id=main&after=0&limit=100
```

Use the largest returned `seq` as the next `after`.

### Read browser state

```
GET /api/state?agent_id=main
```

### Read latest screenshot

```
GET /api/screenshot/latest?agent_id=main
```

The screenshot is stored in R2 and returned as JPEG.

## Local API client

From the repository root:

```powershell
$env:CF_CONTROL_URL="https://shisetsu-browser-control.<your-subdomain>.workers.dev"
$env:CF_CONTROL_TOKEN="<token>"

py -3.12 .\cloudflare_client.py state
py -3.12 .\cloudflare_client.py events --after 0
py -3.12 .\cloudflare_client.py send browser_status --id test-status-1
py -3.12 .\cloudflare_client.py get test-status-1
```

Example relative click:

```powershell
py -3.12 .\cloudflare_client.py send browser_click_relative --id click-1 --args "{\"rx\":0.5,\"ry\":0.8}"
```

## Security

- Chrome CDP remains bound to localhost.
- No inbound port is opened on the Windows PC.
- The PC initiates the WSS connection to Cloudflare.
- The Worker API and WSS handshake require `CONTROL_TOKEN`.
- Browser navigation still uses the existing domain allowlist.
- Authorization/cookie headers are redacted from captured browser traffic.
- Never commit the control token.


## Validated deployment

As of 2026-09-28 the control plane has been deployed and tested successfully.

Validated Worker:

```
https://shisetsu-browser-control.braian-n-l.workers.dev
```

Validated health check:

```powershell
Invoke-RestMethod "https://shisetsu-browser-control.braian-n-l.workers.dev/health"
```

Observed response:

```
ok=True
service=shisetsu-browser-control
```

Validated browser-agent path:

```
Cloudflare API
→ Durable Object
→ persistent WSS
→ Windows agent
→ BrowserController
→ Chrome
→ result
→ D1
```

Validated command lifecycle for `browser_status`:

```
sent → running → done
```

Observed result:

```
connected=true
url=about:blank
viewport=1440x1000
```

The GitHub command queue remains as a fallback only.

## Current auth behavior

The Worker, WSS client, and Python API client use:

```
X-Control-Token: <CONTROL_TOKEN>
```

Do not use the older `Authorization: Bearer ...` examples.

## Next development step

Add a remote MCP surface to this same Worker so ChatGPT can call the browser tools directly through Cloudflare. Reuse the same Durable Object / WSS path rather than opening another transport to the Windows machine.

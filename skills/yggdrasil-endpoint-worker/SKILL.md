---
name: yggdrasil-endpoint-worker
description: Resume and operate the Shisetsu Browser MCP + Endpoints workflow for interactive Yggdrasil demo analysis, including visual clicks, network capture, bonus completion checks, and persistence of verified endpoint contracts.
---

# Yggdrasil Endpoint Worker

Use this skill when continuing the Yggdrasil endpoint-analysis project after context loss, a new chat, or a long interruption.

## Repositories

Primary control bridge:

```
Shisetsu-Code/MCP
```

Evidence/output repository:

```
Shisetsu-Code/Endpoints
```

Do not use GitHub Actions or the GitHub command queue for routine click-by-click interaction unless Cloudflare is unavailable. The preferred path is the deployed Cloudflare control plane with a persistent WSS connection to the local Windows agent.

## Architecture

Preferred validated architecture:

```
control client
  ↓ HTTPS
Cloudflare Worker
  ↓
Durable Object
  ↕ persistent WSS
CloudflareBrowserAgent on Windows
  ↓
BrowserController / Playwright
  ↓ CDP 127.0.0.1:9222
Chrome visible
```

Cloudflare resources:

```
Worker URL:
https://shisetsu-browser-control.braian-n-l.workers.dev

Agent ID:
main

D1:
commands
results
events
agent_state

R2:
JPEG screenshots
```

The WSS path and a complete `browser_status` round trip were validated on 2026-09-28.

Start Chrome if needed:

```powershell
.\start-chrome.ps1
```

Start the preferred agent:

```powershell
$env:CF_CONTROL_URL="https://shisetsu-browser-control.braian-n-l.workers.dev"
$env:CF_CONTROL_TOKEN="<secret>"
$env:CF_AGENT_ID="main"
.\run-cloudflare-agent.ps1
```

GitHub command queue remains only as fallback.

## Command protocol

Write a new command to:

```
commands/current.json
```

Every command MUST have a new unique `id`.

Example:

```json
{
  "id": "cmd-example-0001",
  "action": "browser_click",
  "args": {
    "x": 1200,
    "y": 800
  }
}
```

Read the result from:

```
commands/result.json
```

Supported actions:

```
browser_start
browser_status
browser_open
browser_tabs
browser_select_tab
browser_click
browser_click_text
browser_type
browser_press
browser_wait
browser_screenshot
network_clear
network_events
```

Do not post arbitrary shell commands through the queue.

## Screenshots

Preferred screenshot command:

```json
{
  "id": "cmd-shot-XXXX",
  "action": "browser_screenshot",
  "args": {
    "path": "commands/latest.jpg",
    "quality": 55
  }
}
```

The agent publishes:

```
commands/latest.jpg
commands/latest.b64
```

The GitHub connector may fail to read JPG blobs directly. Read `commands/latest.b64` as text, then render it as:

```
data:image/jpeg;base64,<content>
```

JPEG quality 55 is the default working level. Prefer JPEG over PNG for latency and repository size.

## Browser lifecycle

After the local agent is restarted, its in-memory BrowserController is empty even if Chrome is still open.

First send:

```json
{
  "id": "cmd-reconnect-XXXX",
  "action": "browser_start",
  "args": {
    "cdp_url": "http://127.0.0.1:9222",
    "launch_if_unavailable": true,
    "headless": false
  }
}
```

If a command reports:

```
RuntimeError: Browser is not started
```

send `browser_start` again. Do not ask the user to restart unless the local agent itself is dead.

## Allowed navigation

The BrowserController is allowlisted by default for:

```
yggdrasilgaming.com
staticdemo.yggdrasilgaming.com
demo.yggdrasilgaming.com
```

Do not widen the allowlist unnecessarily.

## Yggdrasil protocol family

Observed common endpoint:

```http
POST https://demo.yggdrasilgaming.com/game.web/service?fn=play
Content-Type: application/x-www-form-urlencoded
```

Common bootstrap:

```
GET  fn=translations
POST fn=authenticate
GET  fn=clientinfo
GET  fn=game
GET  fn=restore
```

Common dynamic/session fields include:

```
clientinfo
authorization/session state
wagerid
userId
x-csid / x-crid
runtime balances/results
```

Never treat dynamic values as constants.

## Security requirements

Captured network traffic MUST redact sensitive headers before persistence.

Current BrowserController redacts at least:

```
Authorization
Cookie
Set-Cookie
Proxy-Authorization
```

Do not intentionally persist live bearer tokens, cookies, session secrets, or user credentials.

The project is intended for public/demo game analysis and protocol documentation.

## Evidence standard

A command or endpoint is considered verified only if observed in actual browser traffic.

Do not infer a `cmd` from naming, UI text, another title, or documentation alone.

For each game/action, record:

```
provider
game name
game id
source URL
runtime URL

endpoint
HTTP method
Content-Type

exact observed request body
normalized request fields
dynamic fields

HTTP status
response Content-Type
response body / semantic summary

continuation commands
intermediate choices
completion condition
status: OBSERVED / CAUSAL / COMPLETED / PARTIAL
```

For purchases, verify whether:

1. one request resolves the whole bonus,
2. further `fn=play` calls are required,
3. a player choice appears during the bonus,
4. the server returns a completion marker.

## Persistence

Write final evidence to:

```
Shisetsu-Code/Endpoints/providers/yggdrasil/<gameid>-<slug>/
```

Preferred files:

```
README.md
observed.json
raw/<action>.json
```

Use `PARTIAL` until all intended buy variants and continuations are verified.

Do not overwrite verified evidence with guesses.

## Current analyzed reference game

### 10964 — Vikings Go To Hollywood WildFight RushingWilds

Location:

```
providers/yggdrasil/10964-vikings-go-to-hollywood/
```

Verified buys:

```
BB_2
amount=65
coin=0.1
→ 10 Free Spins

BB_5
amount=390
coin=0.1
→ 10 Free Spins + 1 Berzerk
```

Both use:

```
POST /game.web/service?fn=play
```

Both were observed to resolve the entire feature in one response, with no intermediate choice and explicit free-spin completion.

## Current batch

Game IDs:

```
10894  multifly-2-multimax
10945  3-piggies-of-bank
10911  timber-trail-treasures
10909  giga-zombies-gigablox
10852  gemstone-jam
10981  turbo-gold-deluxe-gigablox
10764  red-dragon-sails
10809  bloody-pesos
```

Partial evidence already exists in `Endpoints` for these titles.

Observed base commands so far:

```
10894 Multifly 2 MultiMax:
  cmd=BASIC
  amount=1
  coin=1

10945 3 Piggies of Bank:
  cmd=BASIC
  amount=1
  coin=1
  continuation observed: cmd=C amount=0

10911 Timber Trail Treasures:
  cmd=
  amount=1
  coin=0.1

10909 Giga Zombies GigaBlox:
  cmd=
  amount=2
  coin=0.1

10852 Gemstone Jam:
  cmd=BASIC
  amount=1
  coin=1

10981 Turbo Gold Deluxe GigaBlox:
  base amount=2 coin=0.1
  continuation observed: cmd=NON_GAMBLE_6 amount=0
```

Red Dragon Sails and Bloody Pesos still need clean base/bonus capture.

Gemstone Jam does not currently have a confirmed Buy Bonus flow; document actual observed game/feature behavior instead of inventing a buy flow.

## Current live game: 10945 — 3 Piggies of Bank

Direct runtime:

```
https://staticdemo.yggdrasilgaming.com/10945/index.html?appsrv=https://demo.yggdrasilgaming.com&boostUrl=/boost/current/boost.js&channel=pc&countryCode=ar&currency=EUR&fullscreen=yes&gameid=10945&key=&lang=en&license=mt&org=Demo&pcUrl=/partnerconnect/current/partnerconnect.js
```

Main BUY menu at bet EUR 1 showed five purchases:

```
DOUBLE       €180
COLLECT      €120
MYSTERY      €150
RANDOM BANK  €150
ALL BANKS    €250
```

Approximate BUY-button centers from the 1440×1000 viewport:

```
DOUBLE       x=573  y=374
COLLECT      x=1147 y=374
MYSTERY      x=573  y=578
RANDOM BANK  x=1147 y=578
ALL BANKS    x=573  y=781
```

Confirmation modal OK center:

```
x≈843
y≈582
```

### Verified purchase: DOUBLE

Observed causal path:

```
BUY
→ DOUBLE €180
→ OK
→ POST fn=play
```

Request:

```
gameid=10945
amount=180
coin=180
cmd=BB_BLUE
clientinfo=<dynamic>
```

Observed endpoint:

```
POST https://demo.yggdrasilgaming.com/game.web/service?fn=play
```

Response:

```
HTTP 200
code=0
bet.status=RESULTED
modeName=BB_BonusBlue
featureIdentifier=bonusBlue
nextCmds=C
clientData.actions contains the complete bonus sequence
isFinished=true
```

The DOUBLE purchase was observed to resolve the bonus sequence in the response and finish with `isFinished=true`.

Additional verified purchases:

### COLLECT

```
amount=120
coin=120
cmd=BB_GREEN
modeName=BB_BonusGreen
featureIdentifier=bonusGreen
isFinished=true
```

Observed as one complete server-resolved bonus response with no intermediate player choice.

### MYSTERY

```
amount=150
coin=150
cmd=BB_RED
modeName=BB_BonusRed
featureIdentifier=bonusRed
isFinished=true
```

Observed as one complete server-resolved bonus response with no intermediate player choice.

Still pending on 3 Piggies:

```
RANDOM BANK
ALL BANKS
```

For each pending buy:

1. return/open BUY menu,
2. `network_clear`,
3. select the intended BUY button,
4. confirm,
5. query `network_events` with `contains="fn=play"`,
6. inspect request and response,
7. screenshot if the UI presents a choice,
8. continue until the feature is finished,
9. persist evidence to Endpoints.

## Working style

Speed matters.

Prefer:

```
one persistent Chrome
direct runtime URLs
visual targeted clicks
network capture immediately after each action
multiple game results persisted in batches
```

Avoid:

```
repeated GitHub Actions for individual clicks
broad coordinate grid scans when the UI is visible
reinstalling Chromium
re-discovering known game IDs
long speculative analysis before executing
```

If context is limited, first read:

```
skills/yggdrasil-endpoint-worker/SKILL.md
COMMANDS.md
commands/result.json
Shisetsu-Code/Endpoints relevant observed.json files
```

Then continue from the first pending verified action.


## Cloudflare realtime transport

Preferred transport once deployed:

```
control client
→ Cloudflare Worker HTTPS API
→ Durable Object
↔ persistent WSS
→ local CloudflareBrowserAgent
→ Playwright/CDP
→ Chrome
```

Cloudflare files live under:

```
cloudflare/
```

Windows agent:

```
run-cloudflare-agent.ps1
```

Python agent module:

```
src/browser_mcp/cloudflare_agent.py
```

D1 stores command state, results, events, and agent state. R2 stores JPEG screenshots.

Use GitHub only for final evidence once Cloudflare transport is active.

For deployment and environment setup, read:

```
cloudflare/README.md
```


## Validated Cloudflare control state

A full control round trip has been confirmed:

```
POST command
→ status sent
→ WSS delivery
→ local execution
→ status running
→ status done
→ result persisted in D1
```

Validated test command:

```
browser_status
```

Observed result:

```
connected=true
url=about:blank
pages=1
network_events=0
viewport=1440x1000
```

Authentication uses:

```
X-Control-Token: <CONTROL_TOKEN>
```

Do not use the old Authorization Bearer header.

## Preferred command batching

Use `sequence` whenever multiple browser actions belong to one causal operation.

Example:

```
network_clear
→ browser_click_relative
→ browser_click_relative
→ network_wait(contains="fn=play")
```

This executes locally over one WSS command and avoids repeated control-plane round trips.

## Next step after context loss

The next infrastructure task is to expose a remote MCP interface on the Cloudflare Worker itself so ChatGPT can invoke the browser-control operations directly.

Until that exists, `cloudflare_client.py` is the validated control client.

After the MCP surface is implemented, continue Yggdrasil work from:

```
10945 3 Piggies of Bank
pending:
- RANDOM BANK
- ALL BANKS
```

Then persist the complete 10945 evidence to `Shisetsu-Code/Endpoints` and move to the next game in the batch.

# Shisetsu Browser MCP

Servidor de control persistente para navegador mediante Playwright/CDP, con dos transportes: MCP local y un control plane remoto sobre Cloudflare Worker + Durable Object + WSS.

Está pensado para análisis visual y de red de demos web: el navegador permanece abierto entre llamadas, de modo que el cliente puede mirar una captura, hacer clic, inspeccionar tráfico y continuar desde el mismo estado.

## Herramientas

- `browser_start`: conecta a Chrome por CDP o lanza Chromium.
- `browser_status`: estado del navegador.
- `browser_open`: abre una URL permitida.
- `browser_tabs` / `browser_select_tab`: pestañas.
- `browser_click`: clic por coordenadas.
- `browser_click_text`: clic por texto visible.
- `browser_type`: escribe en el control enfocado.
- `browser_press`: teclado.
- `browser_wait`: espera manteniendo la sesión viva.
- `browser_screenshot`: devuelve una captura PNG como contenido visual MCP.
- `network_clear`: limpia la captura.
- `network_events`: requests y responses capturadas, con body textual cuando está disponible.
- `browser_eval`: JavaScript opcional, deshabilitado por defecto.

## Seguridad por defecto

El servidor escucha sólo en:

```
127.0.0.1:8765
```

y `browser_open` sólo admite por defecto:

```
yggdrasilgaming.com
staticdemo.yggdrasilgaming.com
demo.yggdrasilgaming.com
```

No expongas directamente el puerto 8765 ni Chrome CDP 9222 a Internet.

Para cambiar dominios:

```powershell
$env:MCP_ALLOWED_HOSTS="yggdrasilgaming.com,example.com"
```

Para habilitar `browser_eval`:

```powershell
$env:MCP_ENABLE_EVAL="1"
```

## Windows

Clonar:

```powershell
git clone https://github.com/Shisetsu-Code/MCP.git
cd MCP
```

### Opción A — Chrome visible existente

Arrancar Chrome controlable:

```powershell
.\start-chrome.ps1
```

Luego arrancar MCP:

```powershell
.\run.ps1
```

El endpoint queda en:

```
http://127.0.0.1:8765/mcp
```

Al invocar:

```
browser_start(
  cdp_url="http://127.0.0.1:9222",
  launch_if_unavailable=false
)
```

el MCP controla exactamente ese Chrome visible.

### Opción B — Chromium administrado por MCP

Ejecutar sólo:

```powershell
.\run.ps1
```

y llamar:

```
browser_start(headless=false)
```

Si no existe un CDP en 9222, Playwright lanza Chromium visible.

## Prueba local

Con el servidor ejecutándose:

```powershell
.\.venv\Scripts\python.exe test_client.py
```

Esto conecta un cliente MCP al servidor, enumera las herramientas, arranca el navegador y pide su estado.

## Flujo esperado para Yggdrasil

Un cliente puede ejecutar de forma interactiva:

```
browser_start
network_clear
browser_open(<runtime>)
browser_wait(3000)
browser_screenshot
browser_click(x, y)
browser_screenshot
network_events(contains="fn=play")
```

El navegador y la captura de red siguen vivos entre esas llamadas.

## Control remoto Cloudflare

El transporte interactivo preferido ya no es GitHub. El sistema validado usa:

```
control client
→ Cloudflare Worker HTTPS API
→ Durable Object
↔ WSS persistente
→ agente Windows
→ Playwright/CDP
→ Chrome
```

Estado validado:

```
Worker: shisetsu-browser-control
URL: https://shisetsu-browser-control.braian-n-l.workers.dev
Agent ID: main
D1: activo
R2: activo
WSS persistente: validado
browser_status: validado end-to-end
```

El agente local se inicia con:

```powershell
$env:CF_CONTROL_URL="https://shisetsu-browser-control.braian-n-l.workers.dev"
$env:CF_CONTROL_TOKEN="<secret>"
$env:CF_AGENT_ID="main"
.\run-cloudflare-agent.ps1
```

El API local de prueba usa `X-Control-Token` y el cliente `cloudflare_client.py`.

Prueba validada:

```powershell
py -3.12 .\cloudflare_client.py state
py -3.12 .\cloudflare_client.py send browser_status --id test-status-1
py -3.12 .\cloudflare_client.py get test-status-1
```

El resultado observado fue `status: done` con `connected: true`.

GitHub queda como almacenamiento/versionado de evidencia final, no como bus de control por clic.

### Siguiente paso

Exponer un MCP remoto sobre el mismo Worker para que ChatGPT pueda invocar directamente:

```
browser_status
browser_open
browser_click_relative
browser_screenshot
network_clear
network_wait
sequence
```

sin depender del cliente Python manual.

Nunca exponer directamente CDP 9222 ni el MCP local 8765 a Internet.

## Variables

| Variable | Default | Uso |
| --- | --- | --- |
| `MCP_HOST` | `127.0.0.1` | bind del MCP |
| `MCP_PORT` | `8765` | puerto |
| `MCP_ALLOWED_HOSTS` | Yggdrasil | allowlist para navegación |
| `MCP_ENABLE_EVAL` | `0` | habilitar JS |
| `MCP_MAX_BODY_CHARS` | `250000` | límite de body capturado |
| `MCP_MAX_NETWORK_EVENTS` | `5000` | buffer de red |


## Recovery skill

Para retomar el proyecto en una conversación nueva o después de perder contexto, leer primero:

```
skills/yggdrasil-endpoint-worker/SKILL.md
```

Ese archivo contiene la arquitectura del worker, protocolo de comandos, estado actual de los juegos, evidencia verificada y próximos pasos.

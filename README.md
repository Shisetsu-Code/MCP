# Shisetsu Browser MCP

Servidor MCP local para que un cliente MCP controle un navegador persistente mediante Playwright/CDP.

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

## Conexión remota

Este proyecto expone Streamable HTTP MCP en `/mcp`. El SDK oficial de MCP v2 soporta este transporte.

ChatGPT no se conecta directamente a un MCP que sólo existe en `localhost`. Para usar una máquina local con un producto que admita MCP remoto, hay que proporcionar un transporte/túnel compatible. No publiques directamente `8765` o `9222`.

La visibilidad pública/privada de este repositorio no cambia eso: el componente que debe ser alcanzable es el servidor MCP en ejecución, no GitHub.

## Variables

| Variable | Default | Uso |
| --- | --- | --- |
| `MCP_HOST` | `127.0.0.1` | bind del MCP |
| `MCP_PORT` | `8765` | puerto |
| `MCP_ALLOWED_HOSTS` | Yggdrasil | allowlist para navegación |
| `MCP_ENABLE_EVAL` | `0` | habilitar JS |
| `MCP_MAX_BODY_CHARS` | `250000` | límite de body capturado |
| `MCP_MAX_NETWORK_EVENTS` | `5000` | buffer de red |

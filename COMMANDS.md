# Command queue

El agente local observa `commands/current.json`. Cada comando necesita un `id` nuevo.

Ejemplo:

```json
{
  "id": "cmd-0002",
  "action": "browser_click",
  "args": {
    "x": 1210,
    "y": 575
  }
}
```

El resultado aparece en:

```
commands/result.json
```

Acciones soportadas:

- `browser_start`
- `browser_status`
- `browser_open`
- `browser_click`
- `browser_click_text`
- `browser_type`
- `browser_press`
- `browser_wait`
- `browser_tabs`
- `browser_select_tab`
- `browser_screenshot`
- `network_clear`
- `network_events`

Ejemplo para iniciar Chrome:

```json
{
  "id": "cmd-start-1",
  "action": "browser_start",
  "args": {
    "cdp_url": "http://127.0.0.1:9222",
    "launch_if_unavailable": true,
    "headless": false
  }
}
```

Ejemplo para leer tráfico Yggdrasil:

```json
{
  "id": "cmd-net-1",
  "action": "network_events",
  "args": {
    "contains": "fn=play",
    "limit": 50
  }
}
```

El agente valida el nombre de la acción y sólo ejecuta operaciones explícitamente soportadas.

import { DurableObject } from "cloudflare:workers";
import { createMcpHandler } from "agents/mcp/server";
import { McpServer } from "@modelcontextprotocol/server";
import { z } from "zod";

function json(data, status = 200, headers = {}) {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store",
      ...headers,
    },
  });
}

function isAuthorized(request, env) {
  const expected = env.CONTROL_TOKEN;
  if (!expected) return false;
  return request.headers.get("x-control-token") === expected || request.headers.get("authorization") === `Bearer ${expected}`;
}

function safeAgentId(value) {
  const id = (value || "default").trim();
  if (!/^[A-Za-z0-9_.-]{1,64}$/.test(id)) {
    throw new Error("invalid agent_id");
  }
  return id;
}

async function readJson(request) {
  try {
    return await request.json();
  } catch {
    throw new Error("invalid JSON body");
  }
}

function nowMs() {
  return Date.now();
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (url.pathname === "/health") {
      return json({ ok: true, service: "shisetsu-browser-control" });
    }

    if (!isAuthorized(request, env)) {
      return json({ ok: false, error: "unauthorized" }, 401);
    }

    if (url.pathname.startsWith("/mcp")) {\n      return createMcpHandler(() => createBrowserMcpServer(env))(request, env, ctx);\n    }\n\n    if (url.pathname === "/ws") {
      if (request.headers.get("upgrade")?.toLowerCase() !== "websocket") {
        return json({ ok: false, error: "websocket upgrade required" }, 426);
      }
      let agentId;
      try {
        agentId = safeAgentId(url.searchParams.get("agent_id"));
      } catch (error) {
        return json({ ok: false, error: String(error) }, 400);
      }
      const id = env.CONTROL.idFromName(agentId);
      const stub = env.CONTROL.get(id);
      const headers = new Headers(request.headers);
      headers.set("x-agent-id", agentId);
      return stub.fetch(new Request("https://control.internal/ws", {
        method: "GET",
        headers,
      }));
    }

    if (url.pathname === "/api/rpc" && request.method === "POST") {
      let body;
      try {
        body = await readJson(request);
      } catch (error) {
        return json({ ok: false, error: String(error) }, 400);
      }

      let agentId;
      try {
        agentId = safeAgentId(body.agent_id || "firetrace");
      } catch (error) {
        return json({ ok: false, error: String(error) }, 400);
      }

      const command = {
        id: String(body.id || crypto.randomUUID()),
        action: String(body.action || ""),
        args: body.args && typeof body.args === "object" ? body.args : {},
      };

      if (!/^[A-Za-z0-9_.:-]{1,128}$/.test(command.id)) {
        return json({ ok: false, error: "invalid command id" }, 400);
      }
      if (!/^[A-Za-z0-9_.:-]{1,128}$/.test(command.action)) {
        return json({ ok: false, error: "invalid action" }, 400);
      }

      const waitMs = Math.max(
        0,
        Math.min(25000, Number(body.wait_ms ?? 12000) || 12000),
      );

      try {
        await env.DB.prepare(
          `INSERT INTO commands
           (id, agent_id, action, args_json, status, created_at)
           VALUES (?, ?, ?, ?, 'pending', ?)`
        ).bind(
          command.id,
          agentId,
          command.action,
          JSON.stringify(command.args),
          nowMs(),
        ).run();
      } catch (error) {
        if (!String(error).toLowerCase().includes("unique")) throw error;
      }

      const stub = env.CONTROL.get(env.CONTROL.idFromName(agentId));
      const delivered = await stub.fetch("https://control.internal/command", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(command),
      });
      const delivery = await delivered.json();

      if (!delivery.connected) {
        return json({
          ok: false,
          id: command.id,
          agent_id: agentId,
          status: "pending",
          connected: false,
          error: "agent not connected",
        }, 503);
      }

      const deadline = nowMs() + waitMs;
      while (nowMs() <= deadline) {
        const row = await env.DB.prepare(
          "SELECT status, result_json, error, started_at, finished_at FROM commands WHERE id = ?"
        ).bind(command.id).first();

        if (row?.status === "done") {
          return json({
            ok: true,
            id: command.id,
            agent_id: agentId,
            status: "done",
            result: row.result_json ? JSON.parse(row.result_json) : null,
            started_at: row.started_at ?? null,
            finished_at: row.finished_at ?? null,
          });
        }

        if (row?.status === "error") {
          return json({
            ok: false,
            id: command.id,
            agent_id: agentId,
            status: "error",
            error: row.error || "command failed",
            started_at: row.started_at ?? null,
            finished_at: row.finished_at ?? null,
          }, 502);
        }

        if (waitMs === 0) break;
        await new Promise((resolve) => setTimeout(resolve, 100));
      }

      return json({
        ok: true,
        id: command.id,
        agent_id: agentId,
        status: "running",
        connected: true,
      }, 202);
    }

    if (url.pathname === "/api/command" && request.method === "POST") {
      let body;
      try {
        body = await readJson(request);
      } catch (error) {
        return json({ ok: false, error: String(error) }, 400);
      }

      let agentId;
      try {
        agentId = safeAgentId(body.agent_id);
      } catch (error) {
        return json({ ok: false, error: String(error) }, 400);
      }

      const command = {
        id: String(body.id || crypto.randomUUID()),
        action: String(body.action || ""),
        args: body.args && typeof body.args === "object" ? body.args : {},
      };

      if (!/^[A-Za-z0-9_.:-]{1,128}$/.test(command.id)) {
        return json({ ok: false, error: "invalid command id" }, 400);
      }
      if (!/^[A-Za-z0-9_.:-]{1,128}$/.test(command.action)) {
        return json({ ok: false, error: "invalid action" }, 400);
      }

      const createdAt = nowMs();
      try {
        await env.DB.prepare(
          `INSERT INTO commands
           (id, agent_id, action, args_json, status, created_at)
           VALUES (?, ?, ?, ?, 'pending', ?)`
        ).bind(
          command.id,
          agentId,
          command.action,
          JSON.stringify(command.args),
          createdAt,
        ).run();
      } catch (error) {
        if (String(error).toLowerCase().includes("unique")) {
          return json({ ok: false, error: "command id already exists" }, 409);
        }
        throw error;
      }

      const stub = env.CONTROL.get(env.CONTROL.idFromName(agentId));
      const delivered = await stub.fetch("https://control.internal/command", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(command),
      });
      const delivery = await delivered.json();

      return json({
        ok: true,
        id: command.id,
        agent_id: agentId,
        status: delivery.connected ? "sent" : "pending",
        connected: Boolean(delivery.connected),
      }, 202);
    }

    if (url.pathname.startsWith("/api/command/") && request.method === "GET") {
      const id = decodeURIComponent(url.pathname.slice("/api/command/".length));
      const row = await env.DB.prepare(
        "SELECT * FROM commands WHERE id = ?"
      ).bind(id).first();
      if (!row) return json({ ok: false, error: "not found" }, 404);
      return json({
        ok: true,
        command: {
          ...row,
          args: JSON.parse(row.args_json || "{}"),
          result: row.result_json ? JSON.parse(row.result_json) : null,
        },
      });
    }

    if (url.pathname === "/api/events" && request.method === "GET") {
      let agentId;
      try {
        agentId = safeAgentId(url.searchParams.get("agent_id"));
      } catch (error) {
        return json({ ok: false, error: String(error) }, 400);
      }
      const after = Math.max(0, Number(url.searchParams.get("after") || "0") || 0);
      const limit = Math.max(1, Math.min(500, Number(url.searchParams.get("limit") || "100") || 100));

      const rows = await env.DB.prepare(
        `SELECT seq, agent_id, ts, type, command_id, payload_json
         FROM events
         WHERE agent_id = ? AND seq > ?
         ORDER BY seq ASC
         LIMIT ?`
      ).bind(agentId, after, limit).all();

      return json({
        ok: true,
        events: rows.results.map((row) => ({
          seq: row.seq,
          agent_id: row.agent_id,
          ts: row.ts,
          type: row.type,
          command_id: row.command_id,
          payload: JSON.parse(row.payload_json || "{}"),
        })),
      });
    }

    if (url.pathname === "/api/state" && request.method === "GET") {
      let agentId;
      try {
        agentId = safeAgentId(url.searchParams.get("agent_id"));
      } catch (error) {
        return json({ ok: false, error: String(error) }, 400);
      }

      const row = await env.DB.prepare(
        "SELECT * FROM agent_state WHERE agent_id = ?"
      ).bind(agentId).first();

      return json({
        ok: true,
        state: row ? {
          ...row,
          connected: Boolean(row.connected),
          meta: JSON.parse(row.meta_json || "{}"),
        } : null,
      });
    }

    if (url.pathname === "/api/screenshot/latest" && request.method === "GET") {
      let agentId;
      try {
        agentId = safeAgentId(url.searchParams.get("agent_id"));
      } catch (error) {
        return json({ ok: false, error: String(error) }, 400);
      }

      const row = await env.DB.prepare(
        "SELECT screenshot_key FROM agent_state WHERE agent_id = ?"
      ).bind(agentId).first();

      if (!row?.screenshot_key) {
        return json({ ok: false, error: "no screenshot" }, 404);
      }

      const object = await env.SCREENSHOTS.get(row.screenshot_key);
      if (!object) return json({ ok: false, error: "screenshot missing" }, 404);

      const headers = new Headers();
      object.writeHttpMetadata(headers);
      headers.set("etag", object.httpEtag);
      headers.set("cache-control", "no-store");
      if (!headers.has("content-type")) headers.set("content-type", "image/jpeg");
      return new Response(object.body, { headers });
    }

    return json({ ok: false, error: "not found" }, 404);
  },
};

export class ControlSession extends DurableObject {
  constructor(ctx, env) {
    super(ctx, env);
    this.ctx = ctx;
    this.env = env;
  }

  async fetch(request) {
    const url = new URL(request.url);

    if (url.pathname === "/ws") {
      const agentId = request.headers.get("x-agent-id") || "default";
      const pair = new WebSocketPair();
      const [client, server] = Object.values(pair);

      server.serializeAttachment({ agent_id: agentId });
      this.ctx.acceptWebSocket(server);

      await this.setConnected(agentId, true, { transport: "wss" });
      this.ctx.waitUntil(this.flushPending(server, agentId));

      return new Response(null, { status: 101, webSocket: client });
    }

    if (url.pathname === "/command" && request.method === "POST") {
      const command = await request.json();
      const sockets = this.ctx.getWebSockets();
      if (!sockets.length) {
        return json({ connected: false });
      }

      for (const socket of sockets) {
        socket.send(JSON.stringify({ type: "command", command }));
      }

      await this.env.DB.prepare(
        "UPDATE commands SET status = 'sent', sent_at = ? WHERE id = ?"
      ).bind(nowMs(), command.id).run();

      return json({ connected: true, sockets: sockets.length });
    }

    return json({ ok: false, error: "not found" }, 404);
  }

  async flushPending(socket, agentId) {
    const rows = await this.env.DB.prepare(
      `SELECT id, action, args_json
       FROM commands
       WHERE agent_id = ? AND status = 'pending'
       ORDER BY created_at ASC
       LIMIT 100`
    ).bind(agentId).all();

    for (const row of rows.results) {
      socket.send(JSON.stringify({
        type: "command",
        command: {
          id: row.id,
          action: row.action,
          args: JSON.parse(row.args_json || "{}"),
        },
      }));
      await this.env.DB.prepare(
        "UPDATE commands SET status = 'sent', sent_at = ? WHERE id = ?"
      ).bind(nowMs(), row.id).run();
    }
  }

  async webSocketMessage(ws, message) {
    const attachment = ws.deserializeAttachment() || {};
    const agentId = attachment.agent_id || "default";

    if (typeof message !== "string") {
      await this.handleBinary(agentId, message);
      return;
    }

    let data;
    try {
      data = JSON.parse(message);
    } catch {
      return;
    }

    await this.touch(agentId);

    if (data.type === "hello") {
      await this.setConnected(agentId, true, data);
      await this.addEvent(agentId, "hello", null, data);
      return;
    }

    if (data.type === "state") {
      await this.updateState(agentId, data.state || {}, data);
      await this.addEvent(agentId, "state", data.command_id || null, data);
      return;
    }

    if (data.type === "started") {
      const id = String(data.id || "");
      await this.env.DB.prepare(
        "UPDATE commands SET status = 'running', started_at = ? WHERE id = ?"
      ).bind(data.started_at ?? Date.now() / 1000, id).run();
      await this.addEvent(agentId, "started", id, data);
      return;
    }

    if (data.type === "result") {
      const id = String(data.id || "");
      const ok = Boolean(data.ok);
      await this.env.DB.prepare(
        `UPDATE commands
         SET status = ?, started_at = ?, finished_at = ?, result_json = ?, error = ?
         WHERE id = ?`
      ).bind(
        ok ? "done" : "error",
        data.started_at ?? null,
        data.finished_at ?? null,
        data.result === undefined ? null : JSON.stringify(data.result),
        data.error ?? null,
        id,
      ).run();
      await this.addEvent(agentId, "result", id, data);
      return;
    }

    if (data.type === "event") {
      await this.addEvent(agentId, String(data.event || "event"), data.command_id || null, data.payload || {});
    }
  }

  async handleBinary(agentId, message) {
    const bytes = message instanceof ArrayBuffer ? new Uint8Array(message) : new Uint8Array(message);
    if (bytes.byteLength < 4) return;

    const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
    const headerLength = view.getUint32(0, false);
    if (headerLength < 2 || headerLength > 65536 || 4 + headerLength > bytes.byteLength) return;

    const headerBytes = bytes.slice(4, 4 + headerLength);
    const payload = bytes.slice(4 + headerLength);
    let header;
    try {
      header = JSON.parse(new TextDecoder().decode(headerBytes));
    } catch {
      return;
    }

    if (header.type !== "screenshot") return;

    const ts = Number(header.ts || nowMs());
    const commandId = String(header.command_id || "shot");
    const key = `screenshots/${agentId}/${ts}-${commandId}.jpg`;

    await this.env.SCREENSHOTS.put(key, payload, {
      httpMetadata: { contentType: "image/jpeg" },
      customMetadata: {
        agent_id: agentId,
        command_id: commandId,
      },
    });

    await this.env.DB.prepare(
      `INSERT INTO agent_state
       (agent_id, connected, last_seen, screenshot_key, meta_json)
       VALUES (?, 1, ?, ?, '{}')
       ON CONFLICT(agent_id) DO UPDATE SET
         connected = 1,
         last_seen = excluded.last_seen,
         screenshot_key = excluded.screenshot_key`
    ).bind(agentId, nowMs(), key).run();

    await this.addEvent(agentId, "screenshot", commandId, {
      key,
      bytes: payload.byteLength,
      quality: header.quality ?? null,
    });
  }

  async webSocketClose(ws) {
    const attachment = ws.deserializeAttachment() || {};
    await this.setConnected(attachment.agent_id || "default", false, {});
  }

  async webSocketError(ws) {
    const attachment = ws.deserializeAttachment() || {};
    await this.setConnected(attachment.agent_id || "default", false, {});
  }

  async setConnected(agentId, connected, meta) {
    await this.env.DB.prepare(
      `INSERT INTO agent_state
       (agent_id, connected, last_seen, meta_json)
       VALUES (?, ?, ?, ?)
       ON CONFLICT(agent_id) DO UPDATE SET
         connected = excluded.connected,
         last_seen = excluded.last_seen,
         meta_json = excluded.meta_json`
    ).bind(agentId, connected ? 1 : 0, nowMs(), JSON.stringify(meta || {})).run();
  }

  async touch(agentId) {
    await this.env.DB.prepare(
      "UPDATE agent_state SET last_seen = ?, connected = 1 WHERE agent_id = ?"
    ).bind(nowMs(), agentId).run();
  }

  async updateState(agentId, state, meta) {
    await this.env.DB.prepare(
      `INSERT INTO agent_state
       (agent_id, connected, last_seen, browser_url, title, viewport_w, viewport_h, meta_json)
       VALUES (?, 1, ?, ?, ?, ?, ?, ?)
       ON CONFLICT(agent_id) DO UPDATE SET
         connected = 1,
         last_seen = excluded.last_seen,
         browser_url = excluded.browser_url,
         title = excluded.title,
         viewport_w = excluded.viewport_w,
         viewport_h = excluded.viewport_h,
         meta_json = excluded.meta_json`
    ).bind(
      agentId,
      nowMs(),
      state.url ?? null,
      state.title ?? null,
      state.viewport?.width ?? null,
      state.viewport?.height ?? null,
      JSON.stringify(meta || {}),
    ).run();
  }

  async addEvent(agentId, type, commandId, payload) {
    await this.env.DB.prepare(
      `INSERT INTO events (agent_id, ts, type, command_id, payload_json)
       VALUES (?, ?, ?, ?, ?)`
    ).bind(agentId, nowMs(), type, commandId, JSON.stringify(payload || {})).run();
  }
}

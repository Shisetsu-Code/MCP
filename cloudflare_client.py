from __future__ import annotations

import argparse
import json
import os
import urllib.request
import urllib.error


def api(path: str, method: str = "GET", body: dict | None = None):
    base = os.environ["CF_CONTROL_URL"].rstrip("/")
    token = os.environ["CF_CONTROL_TOKEN"]
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        base + path,
        method=method,
        data=data,
        headers={
            "X-Control-Token": token,
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 Shisetsu-Control/1.0",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=35) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"HTTP {exc.code} {exc.reason}\n"
            f"URL: {exc.url}\n"
            f"Server: {exc.headers.get('server')}\n"
            f"CF-Ray: {exc.headers.get('cf-ray')}\n"
            f"Body: {body}"
        ) from None


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("state")
    p.add_argument("--agent", default="main")

    p = sub.add_parser("events")
    p.add_argument("--agent", default="main")
    p.add_argument("--after", type=int, default=0)
    p.add_argument("--limit", type=int, default=100)

    p = sub.add_parser("get")
    p.add_argument("id")

    p = sub.add_parser("send")
    p.add_argument("action")
    p.add_argument("--agent", default="main")
    p.add_argument("--id", default=None)
    p.add_argument("--args", default="{}")

    args = parser.parse_args()

    if args.cmd == "state":
        out = api(f"/api/state?agent_id={args.agent}")
    elif args.cmd == "events":
        out = api(f"/api/events?agent_id={args.agent}&after={args.after}&limit={args.limit}")
    elif args.cmd == "get":
        out = api(f"/api/command/{args.id}")
    else:
        payload = {
            "agent_id": args.agent,
            "action": args.action,
            "args": json.loads(args.args),
        }
        if args.id:
            payload["id"] = args.id
        out = api("/api/command", "POST", payload)

    print(json.dumps(out, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

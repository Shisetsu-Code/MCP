from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

ROOT = Path(__file__).resolve().parent
VENV = ROOT / ".venv"
PY = VENV / "Scripts" / "python.exe"
PIP = VENV / "Scripts" / "pip.exe"
LOG_QUEUE: queue.Queue[str] = queue.Queue()


def run(cmd, cwd=ROOT, check=True, capture=True):
    creationflags = 0
    if os.name == "nt":
        creationflags = subprocess.CREATE_NO_WINDOW
    p = subprocess.run(
        cmd,
        cwd=str(cwd),
        text=True,
        capture_output=capture,
        creationflags=creationflags,
    )
    if capture:
        if p.stdout.strip():
            LOG_QUEUE.put(p.stdout.strip())
        if p.stderr.strip():
            LOG_QUEUE.put(p.stderr.strip())
    if check and p.returncode != 0:
        raise RuntimeError(f"{' '.join(map(str, cmd))} failed with {p.returncode}")
    return p


def user_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if value:
        return value
    try:
        p = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             f"[Environment]::GetEnvironmentVariable('{name}','User')"],
            text=True, capture_output=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        return p.stdout.strip()
    except Exception:
        return ""


def ensure_repo_update():
    LOG_QUEUE.put("Updating repository...")
    run(["git", "pull", "--ff-only", "origin", "main"], check=False)


def ensure_venv():
    if not PY.exists():
        LOG_QUEUE.put("Creating Python environment...")
        run(["py", "-3.12", "-m", "venv", str(VENV)])
    LOG_QUEUE.put("Installing/updating dependencies...")
    run([str(PY), "-m", "pip", "install", "-q", "-e", "."])


def start_chrome():
    chrome_candidates = [
        Path(os.environ.get("PROGRAMFILES", "")) / "Google/Chrome/Application/chrome.exe",
        Path(os.environ.get("PROGRAMFILES(X86)", "")) / "Google/Chrome/Application/chrome.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Google/Chrome/Application/chrome.exe",
    ]
    chrome = next((p for p in chrome_candidates if p.exists()), None)
    if not chrome:
        raise RuntimeError("Google Chrome not found.")

    # Reuse an existing CDP Chrome when available.
    import urllib.request
    try:
        with urllib.request.urlopen("http://127.0.0.1:9222/json/version", timeout=1):
            LOG_QUEUE.put("Chrome CDP already running.")
            return
    except Exception:
        pass

    profile = ROOT / ".chrome-profile"
    profile.mkdir(exist_ok=True)
    subprocess.Popen([
        str(chrome),
        "--remote-debugging-port=9222",
        "--remote-debugging-address=127.0.0.1",
        f"--user-data-dir={profile}",
        "about:blank",
    ])
    LOG_QUEUE.put("Chrome started with CDP on 127.0.0.1:9222.")


class ControlApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Shisetsu MCP Control")
        self.geometry("760x500")
        self.minsize(680, 420)
        self.agent: subprocess.Popen | None = None
        self.stop_requested = False

        outer = ttk.Frame(self, padding=14)
        outer.pack(fill="both", expand=True)

        self.status_var = tk.StringVar(value="Starting...")
        ttk.Label(outer, text="Shisetsu MCP Control", font=("Segoe UI", 16, "bold")).pack(anchor="w")
        ttk.Label(outer, textvariable=self.status_var).pack(anchor="w", pady=(2, 10))

        btns = ttk.Frame(outer)
        btns.pack(fill="x", pady=(0, 10))
        self.restart_btn = ttk.Button(btns, text="Restart agent", command=self.restart_agent, state="disabled")
        self.restart_btn.pack(side="left")
        ttk.Button(btns, text="Open repository", command=self.open_repo).pack(side="left", padx=8)

        self.log = tk.Text(outer, wrap="word", height=22)
        self.log.pack(fill="both", expand=True)
        self.log.configure(state="disabled")

        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.after(100, self.pump_log)
        threading.Thread(target=self.bootstrap, daemon=True).start()

    def append(self, text: str):
        self.log.configure(state="normal")
        self.log.insert("end", text + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def pump_log(self):
        try:
            while True:
                self.append(LOG_QUEUE.get_nowait())
        except queue.Empty:
            pass
        self.after(100, self.pump_log)

    def bootstrap(self):
        try:
            self.status_var.set("Updating...")
            ensure_repo_update()
            ensure_venv()
            start_chrome()

            url = user_env("CF_CONTROL_URL")
            token = user_env("CF_CONTROL_TOKEN")
            agent_id = user_env("CF_AGENT_ID") or "main"

            if not url or not token:
                self.status_var.set("Configuration required")
                LOG_QUEUE.put("Cloudflare configuration is missing.")
                LOG_QUEUE.put("Run setup-cloudflare-env.ps1 once, then restart this launcher.")
                return

            os.environ["CF_CONTROL_URL"] = url
            os.environ["CF_CONTROL_TOKEN"] = token
            os.environ["CF_AGENT_ID"] = agent_id

            self.start_agent()
        except Exception as exc:
            self.status_var.set("Error")
            LOG_QUEUE.put(f"ERROR: {type(exc).__name__}: {exc}")

    def start_agent(self):
        env = os.environ.copy()
        creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        self.agent = subprocess.Popen(
            [str(PY), "-m", "browser_mcp.cloudflare_agent"],
            cwd=str(ROOT),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            creationflags=creationflags,
        )
        self.status_var.set("Connected / running")
        self.restart_btn.configure(state="normal")
        LOG_QUEUE.put("Cloudflare WSS agent started.")
        threading.Thread(target=self.read_agent, daemon=True).start()

    def read_agent(self):
        if not self.agent or not self.agent.stdout:
            return
        for line in self.agent.stdout:
            LOG_QUEUE.put(line.rstrip())
        code = self.agent.poll()
        if not self.stop_requested:
            self.status_var.set(f"Agent stopped ({code}); restarting...")
            LOG_QUEUE.put(f"Agent exited with {code}. Restarting in 2 seconds...")
            time.sleep(2)
            try:
                self.start_agent()
            except Exception as exc:
                LOG_QUEUE.put(f"Restart failed: {exc}")

    def restart_agent(self):
        if self.agent and self.agent.poll() is None:
            self.agent.terminate()
            try:
                self.agent.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.agent.kill()
        self.start_agent()

    def open_repo(self):
        os.startfile(ROOT)

    def on_close(self):
        self.stop_requested = True
        if self.agent and self.agent.poll() is None:
            self.agent.terminate()
        self.destroy()


if __name__ == "__main__":
    ControlApp().mainloop()

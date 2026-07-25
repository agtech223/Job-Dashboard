# -*- coding: utf-8 -*-
"""
DASHBOARD SERVER
================
Serves the dashboard and gives it a live line to the internet.

    GET  /              -> dashboard.html
    GET  /api/jobs      -> the scored job set
    POST /api/refresh   -> kicks off a live scrape in a background thread
    GET  /api/status    -> progress of the running scrape (drives the progress bar)
    GET  /api/starred   -> saved/starred job ids
    POST /api/starred   -> persist saved/starred job ids

Start with:  python server.py        (or double-click START-DASHBOARD.bat)
"""
from __future__ import annotations

import io
import json
import os
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import scraper                                    # noqa: E402
from profile import CANDIDATE                     # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DOCS = os.path.join(ROOT, "docs")
PUBLIC = os.path.join(DOCS, "data")

DASHBOARD = os.path.join(DOCS, "index.html")
JOBS_FILE = os.path.join(PUBLIC, "jobs.json")

DATA = os.path.join(HERE, "data")          # machine-local, never committed
STAR_FILE = os.path.join(DATA, "starred.json")

PORT = int(os.environ.get("JOBRADAR_PORT", "8777"))

PROGRESS = {"running": False, "done": 0, "total": 0, "stage": "idle",
            "found": 0, "error": None, "finished_at": None}
_lock = threading.Lock()


def _read(path, default):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return default


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    # ---- plumbing -------------------------------------------------------
    def _send(self, code, body: bytes, ctype="application/json; charset=utf-8"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionAbortedError):
            pass

    def _json(self, obj, code=200):
        self._send(code, json.dumps(obj, ensure_ascii=False).encode("utf-8"))

    def log_message(self, fmt, *args):
        pass                                   # keep the console clean

    # ---- routes ---------------------------------------------------------
    def do_GET(self):
        path = self.path.split("?")[0].rstrip("/") or "/"

        if path in ("/", "/index.html", "/dashboard.html"):
            try:
                with open(DASHBOARD, "rb") as fh:
                    self._send(200, fh.read(), "text/html; charset=utf-8")
            except FileNotFoundError:
                self._send(404, b"dashboard.html not found", "text/plain")
            return

        # also serve the published snapshot at the same path GitHub Pages uses,
        # so the dashboard behaves identically locally and when hosted
        if path.startswith("/data/"):
            name = os.path.basename(path)
            fpath = os.path.join(PUBLIC, name)
            if os.path.isfile(fpath) and name.endswith(".json"):
                with open(fpath, "rb") as fh:
                    self._send(200, fh.read())
            else:
                self._send(404, b'{"error":"not found"}')
            return

        if path == "/api/jobs":
            data = _read(JOBS_FILE, None)
            if data is None:
                data = {"generated_at": None, "candidate": CANDIDATE, "jobs": [],
                        "stats": {}, "thresholds": {"strong": 70, "good": 50, "floor": 22},
                        "empty": True}
            self._json(data)
            return

        if path == "/api/status":
            with _lock:
                self._json(dict(PROGRESS))
            return

        if path == "/api/starred":
            self._json(_read(STAR_FILE, {"starred": [], "hidden": [], "applied": []}))
            return

        self._send(404, b'{"error":"not found"}')

    def do_POST(self):
        path = self.path.split("?")[0].rstrip("/") or "/"

        if path == "/api/refresh":
            with _lock:
                if PROGRESS["running"]:
                    self._json({"ok": False, "reason": "already running",
                                "progress": dict(PROGRESS)})
                    return
                PROGRESS.update({"running": True, "done": 0, "total": 0,
                                 "stage": "Starting", "found": 0, "error": None})
            threading.Thread(target=scraper.refresh_safe, args=(PROGRESS,),
                             daemon=True).start()
            self._json({"ok": True})
            return

        if path == "/api/starred":
            try:
                n = int(self.headers.get("Content-Length", 0))
                payload = json.loads(self.rfile.read(n) or b"{}")
                os.makedirs(DATA, exist_ok=True)
                with open(STAR_FILE, "w", encoding="utf-8") as fh:
                    json.dump(payload, fh)
                self._json({"ok": True})
            except Exception as exc:
                self._json({"ok": False, "error": str(exc)}, 400)
            return

        self._send(404, b'{"error":"not found"}')


def main():
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    except Exception:
        pass

    os.makedirs(DATA, exist_ok=True)
    url = f"http://localhost:{PORT}/"

    print("=" * 62)
    print("  ACADEMIC JOB RADAR")
    print(f"  {CANDIDATE['name']}")
    print("=" * 62)
    if not os.path.exists(JOBS_FILE):
        print("\n  No job data yet -- running a first scrape (about a minute)...\n")
        try:
            scraper.refresh(PROGRESS)
        except Exception as exc:
            print(f"  First scrape failed: {exc}")
    else:
        data = _read(JOBS_FILE, {})
        st = data.get("stats", {})
        print(f"\n  Loaded {st.get('total', 0)} matched positions "
              f"({st.get('strong', 0)} strong)")

    print(f"\n  Dashboard : {url}")
    print("  Stop      : press Ctrl+C in this window\n")

    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Dashboard stopped.")
        server.shutdown()


if __name__ == "__main__":
    main()

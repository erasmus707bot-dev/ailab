"""Lab web server — stdlib only, 127.0.0.1 by default. One page (web/index.html) + a small JSON API.

Flags gate every working endpoint: with `router` off, chat and model lookup answer 403
`not_switched_on` and nothing is sent or spent. There is no endpoint that changes a flag.
"""
from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import __version__, config, store
from .keys import KeyMissing
from .mcp_client import HermesRefused
from .privacy import PrivacyRefused
from .providers import NAMES
from .spend import SpendBlocked
from .transport import HttpError

WEB = Path(__file__).resolve().parent / "web"
MAX_BODY = 1_000_000
PROVIDER_ICONS = {"ollama": "🏠", "openrouter": "🌐", "claude": "✳️", "hf": "🤗", "qwen": "🐉", "kimi": "🌙"}
OFF = {"router": "💬 Ask models", "preview": "👁 Live preview", "agent": "🤖 Agent"}


def _off(flag: str) -> tuple[int, dict]:
    return 403, {"ok": False, "code": "not_switched_on", "flag": flag,
                 "message": f"{OFF[flag]} is not switched on yet. Nothing was sent and nothing was spent.",
                 "fix": "Scott switches features on one at a time (step M7)."}


class App:
    """Holds config + a lazily built Lab, so tests can inject a fake."""

    def __init__(self, cfg: dict | None = None, lab=None):
        self.cfg = cfg or config.load()
        self._lab = lab

    @property
    def lab(self):
        if self._lab is None:
            from .lab import Lab                                    # noqa: PLC0415
            self._lab = Lab(self.cfg)
        return self._lab

    def spend(self) -> dict:
        cap = self.cfg["daily_cap_usd"]
        try:
            spent = float(self.lab.spend.spent_today())
        except Exception:                                           # noqa: BLE001 — Hermes down must not break the page
            spent = None
        return {"today_usd": spent, "cap_usd": cap}

    def state(self) -> dict:
        return {"ok": True, "version": __version__, "mode": self.cfg["mode"], "flags": self.cfg["flags"],
                "spend": self.spend(), "projects": store.projects(), "hermes_url": self.cfg.get("hermes_url") or "",
                "providers": [{"id": n, "icon": PROVIDER_ICONS.get(n, "◆"), "local": n == "ollama"} for n in sorted(NAMES, key=lambda n: n != "ollama")]}

    # ---- routes: (status, body) ----
    def models(self, q: dict) -> tuple[int, dict]:
        if not self.cfg["flags"]["router"]:
            return _off("router")
        pid, prov = (q.get("project") or ["scratch"])[0], (q.get("provider") or [""])[0]
        r = self.lab.list_models(prov, store.project(pid) or {})
        return 200, {"ok": True, "provider": prov, "source": r.get("source"),
                     "models": [m["id"] for m in r.get("models", [])][:500]}

    def chat(self, b: dict) -> tuple[int, dict]:
        if not self.cfg["flags"]["router"]:
            return _off("router")
        proj = store.project(str(b.get("project") or "")) or {"id": "scratch", "name": "Scratch"}
        msgs = b.get("messages")
        if not isinstance(msgs, list) or not msgs:
            return 400, {"ok": False, "code": "bad_args", "message": "Nothing to send."}
        r = self.lab.chat(proj, str(b.get("provider") or ""), str(b.get("model") or ""), msgs,
                          int(b.get("max_tokens") or 1024), task=f"lab:{proj['id']}")
        return 200, {"ok": True, "text": r.text, "provider": r.provider, "model": r.model, "usd": r.usd,
                     "priced": r.priced, "tokens_in": r.tokens_in, "tokens_out": r.tokens_out, "spend": self.spend()}


ERRORS = ((PrivacyRefused, 403, "privacy", "🔒"), (SpendBlocked, 402, "over_cap", "💲"),
          (KeyMissing, 400, "no_key", "🔑"), (HermesRefused, 502, "hermes", "🔌"),
          (HttpError, 502, "provider", "🌐"), (KeyError, 400, "bad_args", "❓"), (ValueError, 400, "bad_args", "❓"))


def make_server(app: App, host: str = "127.0.0.1", port: int = 0) -> ThreadingHTTPServer:
    index = (WEB / "index.html").read_bytes()

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, code: int, body, ctype: str = "application/json") -> None:
            data = body if isinstance(body, bytes) else json.dumps(body, default=str).encode()
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")               # never show a stale layout
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy",
                             "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; "
                             "img-src 'self' data:; connect-src 'self'; frame-ancestors 'self'")
            self.end_headers()
            self.wfile.write(data)

        def _run(self, fn, *args):
            try:
                code, body = fn(*args)
            except tuple(e[0] for e in ERRORS) as e:
                code, kind, icon = next((c, k, i) for t, c, k, i in ERRORS if isinstance(e, t))
                msg = getattr(e, "message", None) or str(e)
                body = {"ok": False, "code": kind, "icon": icon, "message": msg[:400]}
            except Exception as e:                                       # noqa: BLE001
                code, body = 500, {"ok": False, "code": "internal", "icon": "⚠️",
                                   "message": f"{type(e).__name__}: {e}"[:300]}
            self._send(code, body)

        def do_GET(self):                                                # noqa: N802
            u = urlparse(self.path)
            q = parse_qs(u.query)
            if u.path in ("/", "/index.html"):
                return self._send(200, index, "text/html; charset=utf-8")
            if u.path == "/api/state":
                return self._run(lambda: (200, app.state()))
            if u.path == "/api/models":
                return self._run(app.models, q)
            if u.path == "/api/recover":
                return self._run(lambda: (200, {"ok": True, "fields": store.recover((q.get("project") or [""])[0])}))
            return self._send(404, {"ok": False, "code": "not_found"})

        def do_POST(self):                                               # noqa: N802
            n = int(self.headers.get("Content-Length") or 0)
            if n > MAX_BODY:
                return self._send(413, {"ok": False, "code": "too_big"})
            if self.headers.get("Origin") and urlparse(self.headers["Origin"]).netloc != self.headers.get("Host"):
                return self._send(403, {"ok": False, "code": "cross_origin"})
            try:
                b = json.loads(self.rfile.read(n) or b"{}")
            except ValueError:
                return self._send(400, {"ok": False, "code": "bad_json"})
            p = urlparse(self.path).path
            if p == "/api/chat":
                return self._run(app.chat, b)
            if p == "/api/autosave":
                return self._run(lambda: (200, store.autosave(str(b.get("project")), str(b.get("field") or "draft"),
                                                              str(b.get("text") or ""))))
            if p == "/api/projects":
                return self._run(lambda: (200, {"ok": True, "project": store.save_project(
                    str(b.get("name") or ""), bool(b.get("sensitive")))}))
            return self._send(404, {"ok": False, "code": "not_found"})

    return ThreadingHTTPServer((host, port), H)


def serve(host: str = "127.0.0.1", port: int | None = None) -> int:
    app = App()
    port = port or app.cfg["port"]
    try:
        srv = make_server(app, host, port)
    except OSError as e:
        print(f"⚠️ Port {port} is already in use by another program ({e.strerror}). The Lab did not start.\n"
              f"   Pick another: python3 -m ailab serve --port <N>, or set \"port\" in {config.home()}/config.json",
              file=sys.stderr)
        return 2
    on = [k for k, v in app.cfg["flags"].items() if v] or ["none"]
    print(f"AI Lab on http://{host}:{srv.server_address[1]}/  mode={app.cfg['mode']}  on={','.join(on)}",
          file=sys.stderr)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0

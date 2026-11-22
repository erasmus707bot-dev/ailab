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

from . import __version__, agent, compare, config, preview, review, roster, store
from .keys import KeyMissing
from .mcp_client import HermesRefused
from .privacy import PrivacyRefused
from .providers import NAMES
from .spend import SpendBlocked
from .transport import HttpError

WEB = Path(__file__).resolve().parent / "web"
MAX_BODY = 1_000_000
MAX_CAPTURE_BODY = 12_000_000
# Preview pages run untrusted generated code: opaque origin (CSP sandbox), may not frame elsewhere.
PREVIEW_CSP = ("sandbox allow-scripts allow-forms allow-modals; default-src 'self' data: blob:; "
               "style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; "
               "connect-src 'self'; frame-ancestors 'self'; form-action 'none'")
PROVIDER_ICONS = {"ollama": "🏠", "openrouter": "🌐", "claude": "✳️", "hf": "🤗", "qwen": "🐉", "kimi": "🌙"}
OFF = {"router": "💬 Ask models", "preview": "👁 Live preview", "agent": "🤖 Agent", "compare": "⚖️ Compare models"}
# Static comparison page: our own escaped HTML; only an inline theme-toggle script, images inline.
PAGE_CSP = ("default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; img-src data:; "
            "frame-ancestors 'self'; form-action 'none'")


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
                "spend": self.spend(), "projects": store.projects(), "hermes_url": self.cfg.get("hermes_url") or "", "sandbox": preview.sandbox_kind(),
                "providers": [{"id": n, "icon": PROVIDER_ICONS.get(n, "◆"), "local": n == "ollama"} for n in sorted(NAMES, key=lambda n: n != "ollama")]}

    # ---- routes: (status, body) ----
    def models(self, q: dict) -> tuple[int, dict]:
        if not self.cfg["flags"]["router"]:
            return _off("router")
        pid, prov = (q.get("project") or ["scratch"])[0], (q.get("provider") or [""])[0]
        r = self.lab.list_models(prov, store.project(pid) or {})
        ids, picks = roster.arrange(prov, [m["id"] for m in r.get("models", [])], r.get("source") != "hermes",
                                    (self.cfg.get("extra_models") or {}).get(prov))
        return 200, {"ok": True, "provider": prov, "source": r.get("source"), "models": ids[:500], "picks": picks}

    def roster(self, q: dict) -> tuple[int, dict]:
        if not self.cfg["flags"]["router"]:
            return _off("router")
        pid = (q.get("project") or ["scratch"])[0]
        return 200, {"ok": True, "rows": roster.status(self.lab, store.project(pid) or {})}

    # ---- preview (flag `preview`) ----
    @property
    def pv(self):
        if getattr(self, "_pv", None) is None:
            self._pv = preview.Preview()
        return self._pv

    def _pid(self, v) -> str:
        pid = str((v[0] if isinstance(v, list) else v) or "scratch")
        if not store.project(pid):
            raise preview.PreviewError("No such project.", "bad_args", "❓")
        return pid

    def preview_files(self, q: dict) -> tuple[int, dict]:
        if not self.cfg["flags"]["preview"]:
            return _off("preview")
        pid = self._pid(q.get("project"))
        return 200, {"ok": True, "files": preview.list_files(pid), **self.pv.status(pid)}

    def preview_read(self, q: dict) -> tuple[int, dict]:
        if not self.cfg["flags"]["preview"]:
            return _off("preview")
        pid, rel = self._pid(q.get("project")), (q.get("path") or [""])[0]
        return 200, {"ok": True, "path": rel, "text": preview.read_file(pid, rel)}

    def preview_save(self, b: dict) -> tuple[int, dict]:
        if not self.cfg["flags"]["preview"]:
            return _off("preview")
        return 200, preview.save_file(self._pid(b.get("project")), str(b.get("path") or ""), str(b.get("text") or ""))

    def preview_version(self, q: dict) -> tuple[int, dict]:
        if not self.cfg["flags"]["preview"]:
            return _off("preview")
        return 200, {"ok": True, "v": self.pv.version(self._pid(q.get("project")))}

    def preview_capture(self, b: dict) -> tuple[int, dict]:
        if not self.cfg["flags"]["preview"]:
            return _off("preview")
        return 200, preview.save_capture(self._pid(b.get("project")), str(b.get("png") or ""))

    # ---- agent (flag `agent`) ----
    @property
    def agents(self):
        if getattr(self, "_agents", None) is None:
            self._agents = agent.Agents()
        return self._agents

    def agent_start(self, b: dict) -> tuple[int, dict]:
        if not self.cfg["flags"]["agent"]:
            return _off("agent")
        proj = store.project(self._pid(b.get("project")))
        run = self.agents.start(self.lab, self.cfg, proj, str(b.get("provider") or ""), str(b.get("model") or ""),
                                str(b.get("task") or ""))
        return 200, {"ok": True, "run": run.view()}

    def agent_run(self, q: dict) -> tuple[int, dict]:
        if not self.cfg["flags"]["agent"]:
            return _off("agent")
        return 200, {"ok": True, "run": self.agents.get((q.get("id") or [""])[0]).view(), "spend": self.spend()}

    def agent_stop(self, b: dict) -> tuple[int, dict]:
        if not self.cfg["flags"]["agent"]:
            return _off("agent")
        r = self.agents.get(str(b.get("id") or ""))
        r.stop()
        return 200, {"ok": True, "run": r.view()}

    def agent_undo(self, b: dict) -> tuple[int, dict]:
        if not self.cfg["flags"]["agent"]:
            return _off("agent")
        r = self.agents.get(str(b.get("id") or ""))
        try:
            n = int(b.get("n") or 0)
        except (TypeError, ValueError):
            n = 0
        return 200, {"ok": True, **r.undo_step(n), "run": r.view()}

    def agent_approvals(self, q: dict) -> tuple[int, dict]:
        if not self.cfg["flags"]["agent"]:
            return _off("agent")
        return 200, {"ok": True, "items": agent.approvals()}

    # ---- ⚖️ Compare (flag `compare`, M8). Lanes run the agent loop, so 🤖 Agent must be on too. ----
    @property
    def cmps(self):
        if getattr(self, "_cmps", None) is None:
            self._cmps = compare.Comparisons()
        return self._cmps

    def _cmp_res(self, pid: str, cid: str) -> dict:
        live = self.cmps.get(cid)
        return live.view() if live is not None and live.project["id"] == pid else compare.load(pid, cid)

    def compare_start(self, b: dict) -> tuple[int, dict]:
        if not self.cfg["flags"]["compare"]:
            return _off("compare")
        if not self.cfg["flags"]["agent"]:
            return _off("agent")
        proj = store.project(self._pid(b.get("project")))
        c = self.cmps.start(self.lab, self.cfg, proj, str(b.get("task") or ""), b.get("lanes"), b.get("checks"))
        return 200, {"ok": True, "comparison": c.view()}

    def compare_get(self, q: dict) -> tuple[int, dict]:
        if not self.cfg["flags"]["compare"]:
            return _off("compare")
        pid = self._pid(q.get("project"))
        cid = (q.get("id") or [""])[0]
        if not cid:
            return 200, {"ok": True, "items": compare.listing(pid)}
        return 200, {"ok": True, "comparison": self._cmp_res(pid, cid), "spend": self.spend()}

    def compare_stop(self, b: dict) -> tuple[int, dict]:
        if not self.cfg["flags"]["compare"]:
            return _off("compare")
        c = self.cmps.get(str(b.get("id") or ""))
        if c is None:
            raise compare.CompareError("That comparison isn't running.", "state", "⏹")
        c.stop()
        return 200, {"ok": True, "comparison": c.view()}

    def compare_capture(self, b: dict) -> tuple[int, dict]:
        if not self.cfg["flags"]["compare"]:
            return _off("compare")
        pid, cid = self._pid(b.get("project")), str(b.get("id") or "")
        live = self.cmps.get(cid)
        return 200, compare.save_capture(pid, cid, str(b.get("lane")), str(b.get("png") or ""),
                                         live if live is not None and live.project["id"] == pid else None)

    def compare_review(self, b: dict) -> tuple[int, dict]:
        if not self.cfg["flags"]["compare"]:
            return _off("compare")
        pid, cid = self._pid(b.get("project")), str(b.get("id") or "")
        live = self.cmps.get(cid)
        return 200, compare.to_review(self.lab, self.cfg, pid, cid, str(b.get("title") or ""),
                                      str(b.get("writeup") or ""), live if live is not None and live.project["id"] == pid else None)

    # ---- 📋 Review (M6). Not behind a flag: it sends nothing to a model and spends nothing. ----
    def review_list(self, q: dict) -> tuple[int, dict]:
        pid = (q.get("project") or [""])[0]
        out = {"ok": True, "mode": self.cfg["mode"], "held": review.held(),
               "sent": review.sent(self.lab if self.cfg["mode"] == "connected" else None, self.cfg)}
        if pid:
            pid = self._pid(pid)
            cap = review.latest_capture(pid)
            out["project"] = {"id": pid, "models": review.models_used(pid), "capture": cap.name if cap else ""}
        return 200, out

    def review_send(self, b: dict) -> tuple[int, dict]:
        models = b.get("models")
        models = [str(m) for m in models] if isinstance(models, list) else None
        return 200, review.send(self.lab, self.cfg, self._pid(b.get("project")), str(b.get("title") or ""),
                                str(b.get("writeup") or ""), models)

    def review_apply(self, b: dict) -> tuple[int, dict]:
        return 200, review.apply(str(b.get("id") or ""), str(b.get("sha") or ""), str(b.get("confirm") or ""))

    def review_reject(self, b: dict) -> tuple[int, dict]:
        return 200, review.reject(str(b.get("id") or ""))

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

        def _send(self, code: int, body, ctype: str = "application/json", csp: str | None = None) -> None:
            data = body if isinstance(body, bytes) else json.dumps(body, default=str).encode()
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")               # never show a stale layout
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", csp or
                             "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; "
                             "img-src 'self' data:; connect-src 'self'; frame-ancestors 'self'")
            self.end_headers()
            self.wfile.write(data)

        def _run(self, fn, *args):
            try:
                code, body = fn(*args)
            except preview.PreviewError as e:
                code = {"no_sandbox": 503, "sandbox_failed": 502, "outside": 403, "not_found": 404,
                        "too_big": 413}.get(e.code, 400)
                body = {"ok": False, "code": e.code, "icon": e.icon, "message": e.message[:400]}
            except compare.CompareError as e:
                code = {"sensitive": 403, "too_big": 413, "busy": 409, "state": 409, "secret": 422,
                        "not_found": 404}.get(e.code, 400)
                body = {"ok": False, "code": e.code, "icon": e.icon, "message": e.message[:400]}
            except review.ReviewError as e:
                code = {"sensitive": 403, "outside_home": 403, "dotfile": 403, "symlink": 403, "too_big": 413,
                        "stale": 409, "state": 409, "secret": 422}.get(e.code, 400)
                body = {"ok": False, "code": e.code, "icon": e.icon, "message": str(e)[:400]}
            except tuple(e[0] for e in ERRORS) as e:
                code, kind, icon = next((c, k, i) for t, c, k, i in ERRORS if isinstance(e, t))
                msg = getattr(e, "message", None) or str(e)
                body = {"ok": False, "code": kind, "icon": icon, "message": msg[:400]}
            except Exception as e:                                       # noqa: BLE001
                code, body = 500, {"ok": False, "code": "internal", "icon": "⚠️",
                                   "message": f"{type(e).__name__}: {e}"[:300]}
            self._send(code, body)

        def _foreign(self) -> bool:
            """Requests from a sandboxed preview frame (opaque origin) are cross-site: no API for them."""
            return self.headers.get("Sec-Fetch-Site", "same-origin") not in ("same-origin", "none")

        def _preview_page(self, rest: str):
            if not app.cfg["flags"]["preview"]:
                return self._send(403, b"Live preview is not switched on yet.", "text/plain; charset=utf-8")
            pid, _, rel = rest.partition("/")
            try:
                pid = app._pid(pid)
                code, ctype, data = app.pv.get(pid, rel)
            except preview.PreviewError as e:
                code, ctype, data = 503, "text/plain; charset=utf-8", f"{e.icon} {e.message}".encode()
            return self._send(code, data, ctype, csp=PREVIEW_CSP)

        def _compare_page(self, rest: str):
            """/compare-page/<pid>/<cid>/ → saved page · …/lanes/<k>/<rel> → that lane, served from its srt sandbox."""
            if not app.cfg["flags"]["compare"]:
                return self._send(403, b"Compare is not switched on yet.", "text/plain; charset=utf-8")
            parts = rest.split("/", 4)
            try:
                pid, cid = app._pid(parts[0]), parts[1] if len(parts) > 1 else ""
                d = compare.cdir(pid, cid)
                if len(parts) <= 3 and (len(parts) < 3 or parts[2] in ("", "index.html")):
                    f = d / "result.html"
                    if not f.exists():
                        return self._send(404, b"No such comparison.", "text/plain; charset=utf-8")
                    return self._send(200, f.read_bytes(), "text/html; charset=utf-8", csp=PAGE_CSP)
                if parts[2] != "lanes" or len(parts) < 4:
                    return self._send(404, b"Not found.", "text/plain; charset=utf-8")
                root = compare.lane_dir(pid, cid, parts[3]) / "site"
                if not root.is_dir():
                    return self._send(404, b"No such lane.", "text/plain; charset=utf-8")
                code, ctype, data = app.pv.get(compare.lane_key(pid, cid, parts[3]),
                                               parts[4] if len(parts) > 4 else "", root)
            except (preview.PreviewError, compare.CompareError) as e:
                code, ctype, data = 503 if getattr(e, "code", "") in ("no_sandbox", "sandbox_failed") else 400, \
                    "text/plain; charset=utf-8", f"{e.icon} {e.message}".encode()
            return self._send(code, data, ctype, csp=PREVIEW_CSP)

        def do_GET(self):                                                # noqa: N802
            u = urlparse(self.path)
            q = parse_qs(u.query)
            if u.path.startswith("/preview/"):
                return self._preview_page(u.path[len("/preview/"):])
            if u.path.startswith("/compare-page/"):
                return self._compare_page(u.path[len("/compare-page/"):])
            if u.path.startswith("/api/") and self._foreign():
                return self._send(403, {"ok": False, "code": "cross_origin"})
            if u.path in ("/", "/index.html"):
                return self._send(200, index, "text/html; charset=utf-8")
            if u.path == "/icon.svg":
                return self._send(200, (WEB / "icon.svg").read_bytes(), "image/svg+xml")
            if u.path == "/api/state":
                return self._run(lambda: (200, app.state()))
            if u.path == "/api/models":
                return self._run(app.models, q)
            if u.path == "/api/roster":
                return self._run(app.roster, q)
            if u.path == "/api/preview/files":
                return self._run(app.preview_files, q)
            if u.path == "/api/preview/file":
                return self._run(app.preview_read, q)
            if u.path == "/api/preview/version":
                return self._run(app.preview_version, q)
            if u.path == "/api/agent/run":
                return self._run(app.agent_run, q)
            if u.path == "/api/review":
                return self._run(app.review_list, q)
            if u.path == "/api/compare":
                return self._run(app.compare_get, q)
            if u.path == "/api/agent/approvals":
                return self._run(app.agent_approvals, q)
            if u.path == "/api/recover":
                return self._run(lambda: (200, {"ok": True, "fields": store.recover((q.get("project") or [""])[0])}))
            return self._send(404, {"ok": False, "code": "not_found"})

        def do_POST(self):                                               # noqa: N802
            n = int(self.headers.get("Content-Length") or 0)
            p = urlparse(self.path).path
            if n > (MAX_CAPTURE_BODY if p in ("/api/preview/capture", "/api/compare/capture") else MAX_BODY):
                return self._send(413, {"ok": False, "code": "too_big"})
            if (self.headers.get("Origin") and urlparse(self.headers["Origin"]).netloc != self.headers.get("Host")) \
                    or self._foreign():
                return self._send(403, {"ok": False, "code": "cross_origin"})
            if not (self.headers.get("Content-Type") or "").startswith("application/json"):
                return self._send(415, {"ok": False, "code": "json_only"})     # no plain <form> posts
            try:
                b = json.loads(self.rfile.read(n) or b"{}")
            except ValueError:
                return self._send(400, {"ok": False, "code": "bad_json"})
            if p == "/api/chat":
                return self._run(app.chat, b)
            if p == "/api/preview/file":
                return self._run(app.preview_save, b)
            if p == "/api/preview/capture":
                return self._run(app.preview_capture, b)
            if p == "/api/agent/start":
                return self._run(app.agent_start, b)
            if p == "/api/agent/stop":
                return self._run(app.agent_stop, b)
            if p == "/api/agent/undo":
                return self._run(app.agent_undo, b)
            if p == "/api/compare/start":
                return self._run(app.compare_start, b)
            if p == "/api/compare/stop":
                return self._run(app.compare_stop, b)
            if p == "/api/compare/capture":
                return self._run(app.compare_capture, b)
            if p == "/api/compare/review":
                return self._run(app.compare_review, b)
            if p == "/api/review/send":
                return self._run(app.review_send, b)
            if p == "/api/review/apply":
                return self._run(app.review_apply, b)
            if p == "/api/review/reject":
                return self._run(app.review_reject, b)
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
    finally:
        if getattr(app, "_agents", None):
            app._agents.stop_all()
        if getattr(app, "_cmps", None):
            app._cmps.stop_all()
        if getattr(app, "_pv", None):
            app._pv.close()                                         # stop sandboxed preview servers
    return 0

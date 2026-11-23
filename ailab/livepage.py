"""🪞 Show & change (2026-11-23) — a running app's page, Now beside New, through a look-through proxy.

Two loopback ports. NOW passes everything straight to the running app (Hermes on :8780). NEW does the same, except a
page file the agent has CHANGED in this project (repos/<folder>/<web>/…) is served from that changed copy. So "New"
is the real app with only the changed page swapped in — no second copy of the app, no doubled background jobs.

Rules:
  * the app must be on loopback; request headers go through untouched (the app's own owner rules still decide);
  * NEW is look-only: anything but GET/HEAD/OPTIONS is refused unless Scott switches saving on for this session;
  * NEW pages get a CSP that keeps them talking only to the preview itself (changed code is model-written);
  * nothing here writes the real folder. Keep = HELD for Scott's ✅ (same list as the agent's proposals).
Not covered yet: behind-the-scenes (.py) changes — they are listed, not previewed. WebSockets are not passed.
"""
from __future__ import annotations

import http.client
import json
import mimetypes
import re
import shutil
import subprocess
import tempfile
import threading
from html.parser import HTMLParser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from . import agent, config, preview, repos, secretscan

HOP = {"connection", "keep-alive", "proxy-authenticate", "proxy-authorization", "te", "trailers",
       "transfer-encoding", "upgrade", "proxy-connection"}
MAX_HTML, MAX_UP, MAX_PAGES, MAX_CHANGED = 20_000_000, 50_000_000, 300, 200
NEW_CSP = ("default-src 'self' 'unsafe-inline' 'unsafe-eval' data: blob:; "
           "frame-src 'self' http://127.0.0.1:* http://localhost:*; form-action 'self'")
TITLE = re.compile(rb"<title[^>]*>(.*?)</title>", re.I | re.S)
JS_TYPES = {"", "text/javascript", "application/javascript", "module"}


class LiveError(Exception):
    def __init__(self, message: str, code: str = "live", icon: str = "🪞"):
        super().__init__(message)
        self.message, self.code, self.icon = message, code, icon


# ---------- which apps, which pages ----------
def apps(cfg: dict) -> dict[str, dict]:
    """name -> app. Only a linked folder + a loopback http address + a real web folder inside it."""
    ok, out = repos.linked(cfg), {}
    for name, a in (cfg.get("live_apps") or {}).items():
        if not repos.NAME_RX.fullmatch(str(name)) or not isinstance(a, dict):
            continue
        root, web = ok.get(str(a.get("repo") or "")), str(a.get("web") or "").strip("/")
        u = urlparse(str(a.get("url") or ""))
        try:
            port = u.port
        except ValueError:
            port = None
        if not root or u.scheme != "http" or u.hostname not in ("127.0.0.1", "localhost") or not port:
            continue
        if web and not preview.REL.fullmatch(web):
            continue
        if not (root / web).is_dir():
            continue
        out[str(name)] = {"name": str(name), "repo": str(a["repo"]), "web": web, "host": u.hostname, "port": port,
                          "root": root, "webdir": root / web}
    return out


def app_of(cfg: dict, name: str) -> dict:
    a = apps(cfg).get(str(name))
    if not a:
        raise LiveError(f"No app called {name!r} is set up for Show & change. Set up: {', '.join(apps(cfg)) or 'none'}.",
                        "not_found", "❓")
    return a


def pages(app: dict) -> list[dict]:
    out = []
    for f in sorted(app["webdir"].glob("*.html")):
        if f.name.startswith(".") or f.is_symlink() or not f.is_file():
            continue
        try:
            with open(f, "rb") as fh:
                m = TITLE.search(fh.read(4096))
        except OSError:
            continue
        title = re.sub(r"\s+", " ", m.group(1).decode("utf-8", "replace")).strip()[:60] if m else ""
        out.append({"path": "/" if f.name == "index.html" else "/" + f.name, "file": f.name,
                    "title": title or f.stem})
        if len(out) >= MAX_PAGES:
            break
    out.sort(key=lambda p: (p["path"] != "/", p["title"].lower()))
    return out


def is_up(app: dict) -> bool:
    try:
        c = http.client.HTTPConnection(app["host"], app["port"], timeout=1.5)
        c.connect()
        c.close()
        return True
    except OSError:
        return False


# ---------- the changed copies ----------
def _copies(pid: str, app: dict) -> Path:
    return preview.site_dir(pid) / "repos" / app["repo"]


def _differs(copy: Path, real: Path) -> bool:
    try:
        return not (real.is_file() and real.read_bytes() == copy.read_bytes())
    except OSError:
        return True


def changed(pid: str, app: dict) -> dict:
    """Files in this project's copy of the app's folder that differ from the real ones.
    pages = inside the web folder (the preview shows them); other = everything else (listed only)."""
    base, out = _copies(pid, app), {"pages": [], "other": []}
    if not base.is_dir():
        return out
    pre = app["web"] + "/" if app["web"] else ""
    n = 0
    for f in sorted(base.rglob("*")):
        rel = f.relative_to(base).as_posix()
        if f.is_symlink() or not f.is_file() or any(s.startswith(".") for s in rel.split("/")):
            continue
        if _differs(f, app["root"] / rel):
            (out["pages"] if rel.startswith(pre) else out["other"]).append(rel)
            n += 1
            if n >= MAX_CHANGED:
                break
    return out


def overlay(pid: str, app: dict, urlpath: str) -> Path | None:
    """The changed copy that answers this address on the NEW side, if there is one."""
    p = urlpath.split("?", 1)[0].split("#", 1)[0]
    rel = "index.html" if p in ("", "/") else p.lstrip("/")
    cands = [rel] + ([rel + ".html"] if "." not in rel.rsplit("/", 1)[-1] else [])
    pre = app["web"] + "/" if app["web"] else ""
    site = preview.site_dir(pid).resolve()
    for r in cands:
        if not preview.REL.fullmatch(r):
            continue
        f = _copies(pid, app) / (pre + r)
        if f.is_symlink() or not f.is_file() or not _differs(f, app["root"] / (pre + r)):
            continue
        try:
            f.resolve().relative_to(site)
        except ValueError:
            continue
        return f
    return None


def keep(pid: str, app: dict, note: str = "") -> dict:
    """Keep = hold every changed file for Scott's ✅. Nothing is written to the real folder here."""
    ch, held, skipped = changed(pid, app), [], []
    waiting = agent.approvals()
    for rel in ch["pages"] + ch["other"]:
        try:
            target = repos.safe(app["root"], rel)
        except repos.RepoError as e:
            skipped.append(str(e))
            continue
        text = (_copies(pid, app) / rel).read_text(errors="replace")
        if len(text.encode()) > preview.MAX_EDIT or secretscan.has_secret(text):
            skipped.append(f"{rel}: too big, or it holds something that looks like a key — not kept.")
            continue
        for old in waiting:
            if old.get("path") == str(target) and old.get("project") == pid:
                agent.set_approval_state(old["id"], "superseded")
        item = agent.hold_for_approval(pid, "live", str(target), text,
                                       note=f"{app['repo']}: {note}"[:300] if note else app["repo"])
        held.append({"path": rel, "approval": item["id"]})
    return {"held": held, "skipped": skipped}


def discard(pid: str, app: dict) -> dict:
    """Throw away = put this project's copies back to match the real files (a copy with no real file is removed)."""
    ch, n = changed(pid, app), 0
    for rel in ch["pages"] + ch["other"]:
        copy, real = _copies(pid, app) / rel, app["root"] / rel
        try:
            if real.is_file():
                copy.write_bytes(real.read_bytes())
            else:
                copy.unlink()
            n += 1
        except OSError:
            pass
    return {"discarded": n}


# ---------- 🚦 does the new code at least read as code ----------
class _Scripts(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.out, self._kind = [], None

    def handle_starttag(self, tag, attrs):
        if tag == "script":
            a = dict(attrs)
            t = (a.get("type") or "").strip().lower()
            self._kind = None if "src" in a or t not in JS_TYPES else ("mjs" if t == "module" else "js")
            if self._kind:
                self.out.append([self._kind, ""])

    def handle_endtag(self, tag):
        if tag == "script":
            self._kind = None

    def handle_data(self, data):
        if self._kind:
            self.out[-1][1] += data


def _node_check(node: str, code: str, ext: str) -> str:
    d = config.cache_dir() / "livecheck"
    d.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", suffix="." + ext, dir=d, delete=False) as fh:
        fh.write(code)
        name = fh.name
    try:
        r = subprocess.run([node, "--check", name], capture_output=True, text=True, timeout=20)   # parses, never runs
        if r.returncode == 0:
            return ""
        lines = [x for x in (r.stderr or "").splitlines() if x.strip() and name not in x]
        return (next((x for x in lines if "Error" in x), lines[0] if lines else "does not read as code"))[:200]
    except (OSError, subprocess.TimeoutExpired):
        return ""
    finally:
        try:
            Path(name).unlink()
        except OSError:
            pass


def syntax(pid: str, app: dict) -> dict:
    """Parse-only checks on every changed file. Never runs the code."""
    node, ch, out = shutil.which("node"), changed(pid, app), []
    for rel in ch["pages"] + ch["other"]:
        text, ext, msg = (_copies(pid, app) / rel).read_text(errors="replace"), rel.rsplit(".", 1)[-1].lower(), None
        if ext in ("js", "mjs") and node:
            msg = _node_check(node, text, ext)
        elif ext in ("html", "htm") and node:
            sc = _Scripts()
            try:
                sc.feed(text)
            except Exception:                                       # noqa: BLE001 — a page the parser chokes on is not our call
                sc.out = []
            msg = next((m for m in (_node_check(node, code, kind) for kind, code in sc.out if code.strip()) if m), "")
        elif ext == "json":
            try:
                json.loads(text)
                msg = ""
            except ValueError as e:
                msg = str(e)[:200]
        elif ext == "py":
            try:
                compile(text, rel, "exec")                           # compiles, never runs
                msg = ""
            except SyntaxError as e:
                msg = f"line {e.lineno}: {e.msg}"[:200]
        if msg is not None:
            out.append({"file": rel, "ok": not msg, **({"message": msg} if msg else {})})
    return {"files": out, "node": bool(node), "other": ch["other"]}


# ---------- the script every previewed page gets ----------
PICK_JS = r"""(function(){
  if (window.__labLive || window.parent === window) return; window.__labLive = 1;
  var cs = document.currentScript, side = (cs && /side=(\w+)/.exec(cs.src) || [0, "now"])[1];
  var errs = [], blocked = [];
  function post(m){ m.lab = "live"; m.side = side; try { parent.postMessage(m, "*"); } catch (e) {} }
  function report(type){ post({ type: type || "errors", errors: errs, blocked: blocked, title: document.title,
    path: location.pathname + location.search + location.hash }); }
  function add(list, t){ t = String(t).slice(0, 200); if (list.length < 20 && list.indexOf(t) < 0) list.push(t); report(); }
  addEventListener("error", function(e){
    var el = e.target;
    if (el && el !== window && (el.src || el.href)) {
      var u = el.src || el.href, cross = false;
      try { cross = new URL(u, location.href).origin !== location.origin; } catch (x) {}
      add(cross ? blocked : errs, "could not load " + u);
    } else add(errs, e.message || "script error");
  }, true);
  addEventListener("unhandledrejection", function(e){ var r = e.reason; add(errs, "promise: " + (r && r.message || r)); });
  addEventListener("securitypolicyviolation", function(e){ add(blocked, "blocked: " + (e.blockedURI || e.violatedDirective)); });
  var ce = console.error;
  console.error = function(){ try { add(errs, [].slice.call(arguments).map(String).join(" ")); } catch (x) {} return ce.apply(console, arguments); };
  var of = window.fetch;
  if (of) window.fetch = function(){ return of.apply(this, arguments).then(function(r){
    if (r.status === 403) r.clone().json().then(function(j){ if (j && j.error === "look_only") add(blocked, "look-only: a save was not sent"); }).catch(function(){});
    return r; }); };
  addEventListener("load", function(){ setTimeout(function(){ report("loaded"); }, 1500); });
  addEventListener("hashchange", function(){ report("moved"); });
  var on = false, box = null;
  function sel(el){ var parts = [];
    while (el && el.nodeType === 1 && parts.length < 6 && el !== document.documentElement) {
      if (el.id) { parts.unshift("#" + (window.CSS && CSS.escape ? CSS.escape(el.id) : el.id)); break; }
      var i = 1, s = el; while ((s = s.previousElementSibling)) if (s.tagName === el.tagName) i++;
      parts.unshift(el.tagName.toLowerCase() + ":nth-of-type(" + i + ")"); el = el.parentElement; }
    return parts.join(" > "); }
  function place(el){
    if (!box) { box = document.createElement("div");
      box.style.cssText = "position:fixed;z-index:2147483647;pointer-events:none;border:3px solid #c9a54a;background:rgba(201,165,74,.2);border-radius:6px";
      document.documentElement.appendChild(box); }
    var r = el.getBoundingClientRect();
    box.style.left = r.left + "px"; box.style.top = r.top + "px"; box.style.width = r.width + "px"; box.style.height = r.height + "px"; box.style.display = "block"; }
  function hide(ms){ setTimeout(function(){ if (box) box.style.display = "none"; }, ms); }
  addEventListener("mousemove", function(e){ if (on && e.target && e.target.nodeType === 1) place(e.target); }, true);
  addEventListener("click", function(e){
    if (!on) return; e.preventDefault(); e.stopPropagation(); e.stopImmediatePropagation();
    var el = e.target; place(el); on = false; document.documentElement.style.cursor = "";
    post({ type: "picked", el: { selector: sel(el), tag: el.tagName.toLowerCase(), id: el.id || "",
      text: (el.innerText || el.value || el.getAttribute("aria-label") || "").trim().replace(/\s+/g, " ").slice(0, 120),
      html: el.outerHTML.slice(0, 400) } });
    hide(1500);
  }, true);
  addEventListener("message", function(e){ var d = e.data || {}; if (d.lab !== "live") return;
    if (d.type === "pick") { on = !!d.on; document.documentElement.style.cursor = on ? "crosshair" : ""; if (!on && box) box.style.display = "none"; }
    if (d.type === "show" && d.selector) { try { var el = document.querySelector(d.selector);
      if (el) { el.scrollIntoView({ block: "center" }); place(el); hide(2500); } } catch (x) {} }
  });
})();
"""


def inject(data: bytes, side: str) -> bytes:
    tag = b'<script src="/__lab/pick.js?side=' + side.encode() + b'"></script>'
    head = data[:20000]
    m = re.search(rb"<head[^>]*>", head, re.I) or re.search(rb"<html[^>]*>", head, re.I) \
        or re.match(rb"\s*<!doctype[^>]*>", head, re.I)
    at = m.end() if m else 0
    return data[:at] + tag + data[at:]


# ---------- the two look-through ports ----------
class Live:
    def __init__(self, cfg: dict, host: str = "127.0.0.1"):
        self.cfg, self.host = cfg, host
        self.target: dict | None = None            # {"pid", "app"} — one preview at a time (one user)
        self.allow_writes, self.blocked = False, 0
        self._srv: dict[str, ThreadingHTTPServer] = {}
        self._lock = threading.Lock()

    def ports(self) -> dict:
        if self._srv:
            return {s: v.server_address[1] for s, v in self._srv.items()}
        p = self.cfg.get("live_ports") or [8860, 8861]
        return {"now": int(p[0]), "new": int(p[1])}

    def start(self) -> dict:
        with self._lock:
            want = self.ports()
            for side in ("now", "new"):
                if side in self._srv:
                    continue
                try:
                    srv = ThreadingHTTPServer((self.host, want[side]), _handler(self, side))
                except OSError as e:
                    raise LiveError(f"Port {want[side]} is already used by another program ({e.strerror}). "
                                    f"Change \"live_ports\" in {config.home()}/config.json.", "port_busy", "🔌") from e
                srv.daemon_threads = True
                threading.Thread(target=srv.serve_forever, daemon=True).start()
                self._srv[side] = srv
        return self.ports()

    def open(self, pid: str, app: str) -> dict:
        app_of(self.cfg, app)
        ports = self.start()
        if self.target != {"pid": pid, "app": app}:
            self.target, self.allow_writes, self.blocked = {"pid": pid, "app": app}, False, 0
        return ports

    def status_of(self, side: str, path: str) -> int | None:
        """What the app answers for this address on one side (no script added)."""
        if side not in self._srv:
            return None
        try:
            c = http.client.HTTPConnection("127.0.0.1" if self.host in ("", "0.0.0.0") else self.host,
                                           self._srv[side].server_address[1], timeout=15)
            c.request("GET", path.split("#", 1)[0] or "/", headers={"Sec-Fetch-Dest": "empty"})
            r = c.getresponse()
            r.read(1)
            c.close()
            return r.status
        except OSError:
            return None

    def close(self) -> None:
        with self._lock:
            for srv in self._srv.values():
                srv.shutdown()
                srv.server_close()
            self._srv = {}


def _handler(live: Live, side: str):
    class P(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _plain(self, code: int, body, ctype: str = "text/plain; charset=utf-8", csp: str = "") -> None:
            data = body if isinstance(body, bytes) else str(body).encode()
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            if csp:
                self.send_header("Content-Security-Policy", csp)
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(data)

        def _do(self):
            self.close_connection = True
            try:
                self._serve()
            except (BrokenPipeError, ConnectionResetError):
                pass

        def _serve(self):
            if self.path.split("?", 1)[0] == "/__lab/pick.js":
                return self._plain(200, PICK_JS, "application/javascript; charset=utf-8")
            t = live.target
            app = apps(live.cfg).get(t["app"]) if t else None
            if not app:
                return self._plain(503, "🪞 Pick a page in the Lab first (Show & change).")
            if side == "new":
                if self.command not in ("GET", "HEAD", "OPTIONS") and not live.allow_writes:
                    live.blocked += 1
                    return self._plain(403, json.dumps({"ok": False, "error": "look_only", "message":
                                       "👀 The New page is look-only — nothing was saved."}), "application/json")
                if self.command in ("GET", "HEAD"):
                    f = overlay(t["pid"], app, self.path)
                    if f:
                        ctype = mimetypes.guess_type(f.name)[0] or "application/octet-stream"
                        data = f.read_bytes()
                        if ctype == "text/html":
                            data = inject(data, side)
                        if ctype.startswith("text/") or ctype.endswith(("javascript", "json")):
                            ctype += "; charset=utf-8"
                        return self._plain(200, data, ctype, NEW_CSP)
            self._forward(app)

        def _forward(self, app: dict):
            n = int(self.headers.get("Content-Length") or 0)
            if n > MAX_UP:
                return self._plain(413, "Too big for the preview.")
            body = self.rfile.read(n) if n else None
            mine, up = self.headers.get("Host") or "", f"{app['host']}:{app['port']}"
            conn = http.client.HTTPConnection(app["host"], app["port"], timeout=120)
            try:
                conn.putrequest(self.command, self.path, skip_host=True, skip_accept_encoding=True)
                conn.putheader("Host", up)
                for k, v in self.headers.items():                    # untouched: the app's own owner rules decide
                    kl = k.lower()
                    if kl in HOP or kl in ("host", "accept-encoding", "content-length"):
                        continue
                    if kl in ("origin", "referer") and mine:
                        v = re.sub(r"^https?://" + re.escape(mine), "http://" + up, v)
                    conn.putheader(k, v)
                conn.putheader("Accept-Encoding", "identity")
                if body is not None:
                    conn.putheader("Content-Length", str(len(body)))
                conn.endheaders(body)
                r = conn.getresponse()
            except OSError:
                conn.close()
                return self._plain(502, f"🔌 {app['name']} is not answering on {up}. Start it, then press 🔄.")
            try:
                ctype = (r.getheader("Content-Type") or "").lower()
                hdrs = []
                for k, v in r.getheaders():
                    kl = k.lower()
                    if kl in HOP or kl in ("content-length", "x-frame-options", "server", "date"):
                        continue
                    if kl == "content-security-policy":             # the Lab must be allowed to frame the page
                        v = "; ".join(d for d in (x.strip() for x in v.split(";"))
                                      if d and not d.lower().startswith("frame-ancestors"))
                        if not v:
                            continue
                    if kl == "location":
                        v = re.sub(r"^https?://" + re.escape(up), "", v) or "/"
                    hdrs.append((k, v))
                doc = (ctype.startswith("text/html") and self.command != "HEAD"
                       and self.headers.get("Sec-Fetch-Dest", "iframe") in ("iframe", "document", "frame"))
                first = b""
                if doc:
                    first = r.read(MAX_HTML + 1)
                    if len(first) <= MAX_HTML:
                        if re.search(rb"<html|<!doctype", first[:2000], re.I):
                            first = inject(first, side)
                        self.send_response(r.status)
                        for k, v in hdrs:
                            self.send_header(k, v)
                        self.send_header("Content-Length", str(len(first)))
                        if side == "new":
                            self.send_header("Content-Security-Policy", NEW_CSP)
                        self.end_headers()
                        self.wfile.write(first)
                        return
                self.send_response(r.status)
                for k, v in hdrs:
                    self.send_header(k, v)
                cl = r.getheader("Content-Length")
                if cl and not first:
                    self.send_header("Content-Length", cl)
                self.end_headers()
                if self.command == "HEAD":
                    return
                if first:
                    self.wfile.write(first)
                while True:                                           # streams (events, downloads) pass straight through
                    chunk = r.read1(65536)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    self.wfile.flush()
            except OSError:
                pass
            finally:
                conn.close()

        do_GET = do_POST = do_PUT = do_DELETE = do_PATCH = do_HEAD = do_OPTIONS = _do

    return P

"""📸 Before | After pictures for ✋ waiting changes (2026-11-25, Scott: "i have no idea what is being cleared because
it's just code and no image preview").

For a page change (.html / .css / .js) the robot's headless Chrome opens the page twice from two throw-away loopback
servers: Before = the real folder as it is now, After = the same folder with the proposed file swapped in. It finds
the changed spot (the new element, or the CSS rule's elements), unhides it (opens tabs / details), scrolls to it and
marks it with a gold outline on the After side. Phone-sized (412 px) pictures, like Scott reads.

Live mode (the Lab's and Hermes's own pages): Before / After go through a read-only GET proxy to the running program
so the page has real data; After swaps only the proposed file in. Used only when the live page is byte-for-byte the
file on disk (otherwise the swap couldn't be trusted) — else the plain folder copy is used.

Safety: nothing is written to the real folder. The browser only reaches 127.0.0.1 (every other request is aborted),
sends no cookies of Scott's and only GETs; the throw-away servers serve that one folder, read-only, and nothing else.
Changes that can't be pictured (Python, data…) get a plain "nothing to see — it changes how it works" tag.
"""
from __future__ import annotations

import hashlib
import json
import mimetypes
import os
import re
import threading
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import robotcheck

VISUAL = (".html", ".htm", ".css", ".js", ".mjs", ".svg")
PHONE = {"width": 412, "height": 915}
MAX_FILE = 25 * 1024 * 1024
TIMEOUT_MS = 15_000


def kind(rel: str) -> str:
    """'look' — a page you can see · 'works' — changes how it works (nothing to picture)."""
    return "look" if str(rel).lower().endswith(VISUAL) else "works"


# ------------------------------------------------------------------ where the change is (from the diff)
_TAG = re.compile(r"<([a-zA-Z][\w-]*)([^<>]*)>?")
_ATTR = re.compile(r'([\w:-]+)\s*=\s*"([^"]*)"')
_KEEP = ("id", "onclick", "aria-label", "data-tab", "name", "href", "class")


def _q(v: str) -> str:
    return v.replace("\\", "\\\\").replace('"', '\\"')


def _html_sel(line: str) -> str | None:
    m = _TAG.search(line.strip())
    if not m or m.group(1).lower() in ("script", "style", "html", "head", "body", "meta", "link"):
        return None
    attrs = {k.lower(): v for k, v in _ATTR.findall(m.group(2)) if k.lower() in _KEEP and v and "${" not in v}
    if not attrs:
        return None
    return m.group(1).lower() + "".join(f'[{k}="{_q(v)}"]' for k, v in sorted(attrs.items()))


def _css_sels(line: str) -> list[str]:
    s = line.strip()
    if "{" not in s or s.startswith(("@", "/*", "//")):
        return []
    out = []
    for part in s.split("{", 1)[0].split(","):
        p = re.sub(r"::?[\w-]+(\([^)]*\))?", "", part).strip()       # :hover, ::before … can't be queried
        if p and not re.search(r"[{};]", p):
            out.append(p)
    return out


def spots(rel: str, diff: str) -> dict:
    """→ {"after": [selectors…], "before": [selectors…]} — new things first, their neighbours as the fallback."""
    ext = Path(rel).suffix.lower()
    added, near = [], []
    for ln in (diff or "").splitlines():
        if ln.startswith(("+++", "---", "@@")):
            continue
        if ln.startswith("+"):
            added.append(ln[1:])
        elif ln.startswith(" "):
            near.append(ln[1:])
    if ext in (".html", ".htm", ".svg"):
        a = [s for s in map(_html_sel, added) if s]
        n = [s for s in map(_html_sel, near) if s]
    else:
        a, n = [], []
    if ext in (".css", ".html", ".htm"):                              # CSS rules (a .css file, or <style> in a page)
        a += [s for ln in added for s in _css_sels(ln)]
        n += [s for ln in near for s in _css_sels(ln)]
    seen = set()
    a = [s for s in a if not (s in seen or seen.add(s))][:30]
    n = [s for s in n if not (s in seen or seen.add(s))][:30]
    return {"after": a + n, "before": n + a}


# ------------------------------------------------------------------ the page to open
def page_for(target: Path) -> Path | None:
    if target.suffix.lower() in (".html", ".htm", ".svg"):
        return target
    d = target.parent
    for cand in sorted(d.glob("*.htm*")):
        try:
            if cand.stat().st_size < MAX_FILE and target.name in cand.read_text(errors="replace"):
                return cand
        except OSError:
            continue
    idx = d / "index.html"
    return idx if idx.is_file() else None


class _Folder(ThreadingHTTPServer):
    daemon_threads = True


def _serve(root: Path, swap: dict[Path, str]) -> _Folder:
    root = root.resolve()

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):  # noqa: N802
            rel = self.path.split("?", 1)[0].split("#", 1)[0].lstrip("/") or "index.html"
            p = Path(os.path.normpath(root / rel))
            body = None
            try:
                p.relative_to(root)
                if p in swap:
                    body = swap[p].encode()
                elif p.is_file() and not p.is_symlink() and p.stat().st_size <= MAX_FILE:
                    body = p.read_bytes()
            except (ValueError, OSError):
                body = None
            if body is None:
                self.send_response(404)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            self.send_response(200)
            self.send_header("Content-Type", mimetypes.guess_type(p.name)[0] or "application/octet-stream")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

    srv = _Folder(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


_SHOW = """(a) => {
  let el = null;
  for (const s of a.sels) { try { const e = document.querySelector(s); if (e) { el = e; break; } } catch (e) {} }
  if (!el) return {found: false};
  for (let p = el; p && p !== document.documentElement; p = p.parentElement) {
    if (p.tagName === 'DETAILS') p.open = true;
    if (p.hidden) p.hidden = false;
    const cs = getComputedStyle(p);
    if (cs.display === 'none') p.style.setProperty('display', 'block', 'important');
    if (cs.visibility === 'hidden') p.style.setProperty('visibility', 'visible', 'important');
    if (parseFloat(cs.opacity) === 0) p.style.setProperty('opacity', '1', 'important');
  }
  el.scrollIntoView({block: 'center', behavior: 'instant'});
  if (a.mark) { el.style.setProperty('outline', '4px solid #d8b65c', 'important'); el.style.setProperty('outline-offset', '3px', 'important'); }
  return {found: true, tag: el.tagName.toLowerCase()};
}"""


def _real(page_rel: str, before_url: str, after_url: str, sels: dict, out: Path, cfg: dict | None) -> dict:
    from playwright.sync_api import sync_playwright  # noqa: PLC0415
    exe = robotcheck.browser_path(cfg)
    res = {}
    with sync_playwright() as pw:
        b = pw.chromium.launch(headless=True, **({"executable_path": exe} if exe else {}))
        try:
            ctx = b.new_context(viewport=PHONE, device_scale_factor=1.5, java_script_enabled=True)
            ctx.route("**/*", lambda r: r.continue_() if r.request.method == "GET" and
                      re.match(r"^https?://127\.0\.0\.1[:/]", r.request.url) else r.abort())
            for side, url in (("before", before_url), ("after", after_url)):
                page = ctx.new_page()
                errs: list[str] = []
                page.on("pageerror", lambda e, errs=errs: errs.append(str(e)[:160]))
                try:
                    page.goto(url + page_rel, wait_until="load", timeout=TIMEOUT_MS)
                    page.wait_for_timeout(900)
                    f = page.evaluate(_SHOW, {"sels": sels[side], "mark": side == "after"})
                    page.wait_for_timeout(300)
                    shot = out.with_name(out.name + f"-{side}.png")
                    page.screenshot(path=str(shot), full_page=not f.get("found"),
                                    clip=None if f.get("found") else {"x": 0, "y": 0, "width": PHONE["width"], "height": 1800})
                    res[side] = {"found": bool(f.get("found")), "errors": errs[:5]}
                except Exception as e:                                # noqa: BLE001 — a picture that failed is a note
                    res[side] = {"found": False, "error": str(e).splitlines()[0][:200]}
                page.close()
        finally:
            b.close()
    return res


def live_for(target: Path, cfg: dict | None) -> tuple[str, str] | None:
    """(live base URL, page path) when target is a page the running Lab / Hermes serves — else None."""
    cfg = cfg or {}
    g = cfg.get("guarded") or {}
    table = dict(cfg.get("shot_live") or {})
    if g.get("ailab"):
        table.setdefault(str(Path(g["ailab"]) / "ailab" / "web"), "http://127.0.0.1:8850")
    if g.get("hermes"):
        table.setdefault(str(Path(g["hermes"]) / "dist" / "hermes-local" / "hermes_local" / "web"), "http://127.0.0.1:8780")
    page = page_for(target)
    if not page:
        return None
    for d, base in table.items():
        try:
            page.resolve().relative_to(Path(d).resolve())
        except (ValueError, OSError):
            continue
        rel = page.resolve().relative_to(Path(d).resolve())
        path = "/" if str(rel) == "index.html" else "/" + rel.with_suffix("").as_posix()
        return base.rstrip("/"), path
    return None


def _fetch(url: str, timeout: float = 8) -> tuple[int, bytes, str]:
    req = urllib.request.Request(url, headers={"User-Agent": "ailab-shots"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:      # noqa: S310 — loopback only (checked by callers)
            return r.status, r.read(MAX_FILE), r.headers.get("Content-Type", "")
    except urllib.error.HTTPError as e:
        return e.code, e.read(MAX_FILE) if e.fp else b"", e.headers.get("Content-Type", "") if e.headers else ""


def _proxy(base: str, page_path: str, target: Path, swap: str | None) -> _Folder:
    """GET-only proxy to the live program; with swap, the page (or the changed .css/.js) comes from the proposal."""
    assert re.match(r"^http://127\.0\.0\.1:\d+$", base), base

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _out(self, code, body, ctype):
            self.send_response(code)
            self.send_header("Content-Type", ctype or "application/octet-stream")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):  # noqa: N802
            path = self.path.split("#", 1)[0]
            bare = path.split("?", 1)[0]
            if swap is not None and (bare == page_path if target.suffix.lower() in (".html", ".htm")
                                     else bare.rsplit("/", 1)[-1] == target.name):
                return self._out(200, swap.encode(), mimetypes.guess_type(target.name)[0] or "text/html")
            try:
                code, body, ctype = _fetch(base + path)
            except Exception:                                         # noqa: BLE001
                code, body, ctype = 502, b"", "text/plain"
            self._out(code, body, ctype)

        def do_POST(self):  # noqa: N802 — never forward a write
            self._out(403, b"", "text/plain")

    srv = _Folder(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def make(aid: str, target: Path, proposed: str, diff: str, store: Path, cfg: dict | None = None, driver=None) -> dict:
    """Pictures for one waiting change → meta {visual, ran, same, found, why, sha}. Cached by the proposal's sha."""
    sha = hashlib.sha256(f"v2\0{proposed}".encode()).hexdigest()[:16]    # v2 = live mode (2026-11-25)
    base = store / f"{aid}-shots"
    meta_f = store / f"{aid}-shots.json"
    try:
        old = json.loads(meta_f.read_text())
        if old.get("sha") == sha:
            return old
    except (OSError, ValueError):
        pass
    meta: dict = {"sha": sha, "visual": kind(target.name) == "look", "ran": False}
    if not meta["visual"]:
        meta["why"] = "Nothing to picture — this changes how it works, not how it looks."
        meta_f.write_text(json.dumps(meta))
        return meta
    page = page_for(target)
    if not page:
        meta["why"] = "📸 No page found that uses this file, so no pictures."
        meta_f.write_text(json.dumps(meta))
        return meta
    if driver is None:
        ok, msg = robotcheck.available(cfg)
        if not ok:
            meta["why"] = f"📸 No pictures: {msg}"
            return meta                                                  # not cached — try again once it's installed
        driver = _real
    live, page_rel = live_for(target, cfg), page.name
    if live:                                                         # live only if the live page IS the disk file
        try:
            code, body, _ = _fetch(live[0] + live[1])
            ok = code == 200 and (target.suffix.lower() not in (".html", ".htm") or body == target.read_bytes())
        except Exception:                                            # noqa: BLE001
            ok = False
        live = live if ok else None
    if live:
        before, after = _proxy(live[0], live[1], target, None), _proxy(live[0], live[1], target, proposed)
        page_rel = live[1].lstrip("/")
        meta["live"] = True
    else:
        root = page.parent
        before, after = _serve(root, {}), _serve(root, {target.resolve(): proposed})
    try:
        sels = spots(target.name, diff)
        res = driver(page_rel, f"http://127.0.0.1:{before.server_address[1]}/",
                     f"http://127.0.0.1:{after.server_address[1]}/", sels, base, cfg)
    except Exception as e:                                               # noqa: BLE001
        meta["why"] = f"📸 The robot couldn't take pictures: {str(e).splitlines()[0][:200]}"
        return meta
    finally:
        for srv in (before, after):
            srv.shutdown()
            srv.server_close()
    b, a = Path(f"{base}-before.png"), Path(f"{base}-after.png")
    meta.update(ran=b.is_file() and a.is_file(), found=bool((res.get("after") or {}).get("found")), detail=res)
    if meta["ran"]:
        meta["same"] = hashlib.sha256(b.read_bytes()).digest() == hashlib.sha256(a.read_bytes()).digest()
        if meta["same"]:
            meta["why"] = "Looks the same in a picture — the change only shows with real data or after a tap."
        elif not meta["found"]:
            meta["why"] = "Couldn't find the exact spot — showing the top of the page."
    else:
        meta["why"] = "📸 The robot couldn't take pictures: " + "; ".join(
            str(v.get("error") or "") for v in res.values() if isinstance(v, dict))[:200]
    meta_f.write_text(json.dumps(meta))
    return meta


def picture(store: Path, aid: str, side: str) -> bytes | None:
    if side not in ("before", "after") or not re.fullmatch(r"[0-9]{8}-[0-9]{6}-[0-9a-f]{6}", aid or ""):
        return None
    f = store / f"{aid}-shots-{side}.png"
    return f.read_bytes() if f.is_file() else None

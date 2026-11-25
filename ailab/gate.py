"""Who may use the Lab (2026-11-24: the Lab goes online over Scott's tailnet, like Hermes and ERASMUS).

Same rule as Hermes's dashboard (_owner_by_local / Tailscale-User-Login):
  * a request with NO proxy markers from a loopback socket = a browser or process sitting at gandalf → allowed
    (that is also how the Lab's own robot tests and preview helpers reach it);
  * a proxied request (`tailscale serve` adds X-Forwarded-* and Tailscale-User-*) must carry a Tailscale-User-Login
    that is one of Scott's owner logins → allowed;
  * anything else → refused.
Owner logins = Hermes's own list (~/hermes-local/knowledge_base/access/collaborators.json: owner_login +
owner_logins), plus HERMES_OWNER_LOGIN (comma list) and the Lab config "owner_logins". Nothing new to set up."""
from __future__ import annotations

import ipaddress
import json
import os
import time
from pathlib import Path

PROXY_MARKERS = ("x-forwarded-for", "x-forwarded-host", "x-forwarded-proto", "forwarded", "x-real-ip", "via",
                 "tailscale-user-login", "tailscale-user-name")
_CACHE: dict = {"at": 0.0, "logins": frozenset()}
TTL = 60.0

REFUSED_HTML = ("<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>"
                "<title>AI Lab</title><body style='background:#0d1520;color:#e8dfc8;font:17pt/1.5 system-ui;"
                "padding:24px'><h1>🔒 AI Lab</h1><p>Only Scott can use the AI Lab.</p><p style='color:#a9a08c'>"
                "If this is you: turn Tailscale on and make sure it is signed in with your own account, then reload."
                "</p></body>").encode()


def _norm(s) -> str:
    return str(s or "").strip().lower()


def hermes_access_file() -> Path:
    kb = os.environ.get("HERMES_KB") or "~/hermes-local/knowledge_base"
    return Path(kb).expanduser() / "access" / "collaborators.json"


def owner_logins(cfg: dict | None = None, now: float | None = None) -> frozenset:
    now = time.time() if now is None else now
    extra = {_norm(x) for x in ((cfg or {}).get("owner_logins") or []) if _norm(x)}
    if now - _CACHE["at"] > TTL:
        found = {_norm(x) for x in (os.environ.get("HERMES_OWNER_LOGIN") or "").split(",") if _norm(x)}
        try:
            d = json.loads(hermes_access_file().read_text(encoding="utf-8"))
            found |= {_norm(d.get("owner_login"))} | {_norm(x) for x in (d.get("owner_logins") or [])}
        except (OSError, ValueError, AttributeError):
            pass
        _CACHE.update(at=now, logins=frozenset(x for x in found if x))
    return _CACHE["logins"] | frozenset(extra)


def _loopback(addr: str) -> bool:
    try:
        return ipaddress.ip_address(str(addr).split("%")[0]).is_loopback
    except ValueError:
        return False


def _h(headers) -> dict:
    """Case-insensitive view (http.server headers already are; plain dicts in tests are not)."""
    return {str(k).lower(): v for k, v in (headers.items() if hasattr(headers, "items") else [])}


def proxied(headers) -> bool:
    h = _h(headers)
    return any(h.get(k) for k in PROXY_MARKERS)


def allowed(headers, peer: str, cfg: dict | None = None) -> bool:
    """True if this request may use the Lab."""
    if not proxied(headers):
        return _loopback(peer)
    login = _norm(_h(headers).get("tailscale-user-login"))
    return bool(login) and login in owner_logins(cfg)


def remote(headers) -> bool:
    """Reached through Tailscale (so links must use the ts.net name, not 127.0.0.1)."""
    return proxied(headers)

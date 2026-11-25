"""Lab web server — stdlib only, 127.0.0.1 by default. One page (web/index.html) + a small JSON API.

Flags gate every working endpoint: with `router` off, chat and model lookup answer 403
`not_switched_on` and nothing is sent or spent. There is no endpoint that changes a flag.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import (__version__, agent, compare, config, livepage, memory, notify, preview, promptbuilder, repos, review, ship, creation,
               robotcheck, roster, store, guardlink)
from . import looks
from . import video as videomod             # 🛤 video paths (2026-11-24)
from .keys import KeyMissing
from .mcp_client import HermesRefused
from .privacy import PrivacyRefused
from .providers import NAMES
from .spend import SpendBlocked
from .transport import HttpError

_STARTED = int(time.time())                # when this server process started (proves a restart)
WEB = Path(__file__).resolve().parent / "web"
MAX_BODY = 1_000_000
MAX_CAPTURE_BODY = 12_000_000
# Preview pages run untrusted generated code: opaque origin (CSP sandbox), may not frame elsewhere.
# 🎬 long clips (2026-11-24, Scott: "raise the Lab viewer limit so long clips always open"): video/audio are
# streamed in slices with HTTP Range — any length opens and seeks; pages/pictures keep the one-piece path.
MEDIA_EXT = (".mp4", ".webm", ".mov", ".m4v", ".mkv", ".mp3", ".wav", ".ogg", ".oga", ".m4a", ".flac", ".aac", ".opus")
RANGE_CHUNK = 8_000_000          # most bytes in one 206 answer to an open-ended range; the browser asks for more


def parse_range(header: str | None, size: int, cap: int = RANGE_CHUNK):
    """'bytes=a-b' → (start, end) inclusive, end clipped to a+cap-1 and size-1 · None = no/unsupported header
    (send it all) · 'bad' = unsatisfiable (416)."""
    if not header:
        return None
    m = re.fullmatch(r"\s*bytes=(\d*)-(\d*)\s*", header)
    if not m or (not m.group(1) and not m.group(2)):
        return None                                   # multi-range or junk: answer with the whole file
    if not m.group(1):                                # suffix: last n bytes
        n = int(m.group(2))
        if n <= 0 or size <= 0:
            return "bad"
        start = max(0, size - n)
        end = size - 1
    else:
        start = int(m.group(1))
        end = int(m.group(2)) if m.group(2) else size - 1
        if start >= size or end < start:
            return "bad"
        end = min(end, size - 1)
    return start, min(end, start + cap - 1)


PREVIEW_CSP = ("sandbox allow-scripts allow-forms allow-modals; default-src 'self' data: blob:; "
               "style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; "
               "connect-src 'self'; frame-ancestors 'self'; form-action 'none'")
PROVIDER_ICONS = {"ollama": "🏠", "openrouter": "🌐", "claude": "✳️", "hf": "🤗", "qwen": "🐉", "kimi": "🌙", "gemini": "💎"}
OFF = {"router": "💬 Ask models", "preview": "👁 Live preview", "agent": "🤖 Agent", "compare": "⚖️ Compare models",
       "live": "🪞 Show & change", "memory": "🧠 Memory", "prompt": "📝 Prompt builder"}
# Static comparison page: our own escaped HTML; only an inline theme-toggle script, images inline.
PAGE_CSP = ("default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; img-src data:; "
            "frame-ancestors 'self'; form-action 'none'")


LIVE_POST = {"/api/live/open": "live_open", "/api/live/writes": "live_writes", "/api/live/check": "live_check", "/api/live/robot": "live_robot",
             "/api/live/keep": "live_keep", "/api/live/discard": "live_discard"}


def _keyring_ok() -> bool:
    from .keys import _keyring                                     # noqa: PLC0415
    return _keyring() is not None


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
                "spend": self.spend(), "projects": store.projects(), "hermes_url": self.cfg.get("hermes_url") or "", "repos": sorted(repos.linked(self.cfg)), "programs": repos.programs(self.cfg), "sandbox": preview.sandbox_kind(),
                "prompt_writer": self.cfg.get("prompt_writer") or [],
                "providers": [{"id": n, "icon": PROVIDER_ICONS.get(n, "◆"), "local": n == "ollama", **({"off": True} if n in self._hermes_off() else {})}
                              for n in sorted(NAMES, key=lambda n: n != "ollama")],
                # fix 5: what's running / stuck / ended without proof — for the Hermes card (and later Iris "finished or stuck")
                "runs": [{"id": r.id, "project": r.project["id"], "state": r.state, **r.stuck_info(), "proved": r.proof_ok()}
                         for r in list(self.agents.runs.values())[-10:]]}

    def _hermes_off(self) -> set:
        """2026-11-23: hosted providers Hermes has turned off (connected mode) — the page skips them as the default pick.
        Cached 60 s; Hermes down → nothing marked off (the models call still explains)."""
        import time                                                # noqa: PLC0415
        if self.cfg["mode"] != "connected":
            return set()
        c = getattr(self, "_off_cache", None)
        if c and time.monotonic() - c[0] < 60:
            return c[1]
        try:
            listed = {e["provider"] for e in self.lab.mcp.call("llm_providers").get("providers", [])}
            off = {n for n in NAMES if n != "ollama" and n not in listed}
        except Exception:                                          # noqa: BLE001 — Hermes down is a normal state
            off = set()
        self._off_cache = (time.monotonic(), off)
        return off

    # ---- routes: (status, body) ----
    def models(self, q: dict) -> tuple[int, dict]:
        if not self.cfg["flags"]["router"]:
            return _off("router")
        pid, prov = (q.get("project") or ["scratch"])[0], (q.get("provider") or [""])[0]
        r = self.lab.list_models(prov, store.project(pid) or {})
        ids, picks = roster.arrange(prov, [m["id"] for m in r.get("models", [])], r.get("source") != "hermes",
                                    (self.cfg.get("extra_models") or {}).get(prov))
        price_of = None
        try:                                                        # price table for models the listing didn't price
            p = self.lab.provider(prov)
            price_of = lambda mid, listed, _p=p: _p.price(mid, listed)     # noqa: E731
        except Exception:                                           # noqa: BLE001 — fakes / unknown provider: no tiers
            pass
        tg = roster.tags(prov, r.get("models", []), price_of)
        return 200, {"ok": True, "provider": prov, "source": r.get("source"), "models": ids[:500], "picks": picks,
                     "tags": {m: tg.get(m, {"use": roster.use_tag(m), "tier": "", "limits": roster.limits_tag(prov, m)})
                              for m in ids[:500]},
                     "legend": roster.USE_LEGEND}

    # ---- 🔑 Keys page (2026-11-23). Standalone: the Lab's own store (keyring → environment → keys.env, 0600).
    # Connected: Hermes holds every hosted key (Vault) — the Lab shows Hermes's answer and points at Hermes Settings.
    def keys(self, q: dict) -> tuple[int, dict]:
        from .keys import ENV_NAMES                                # noqa: PLC0415
        hosted = [n for n in NAMES if n != "ollama"]
        out = {"ok": True, "mode": self.cfg["mode"], "hermes_url": self.cfg.get("hermes_url") or "", "providers": []}
        if self.cfg["mode"] == "connected":
            known = {}
            try:
                for e in self.lab.mcp.call("llm_providers").get("providers", []):
                    known[e["provider"]] = e
            except Exception as e:                                 # noqa: BLE001 — Hermes down is a normal state
                out["note"] = f"Hermes isn't answering ({type(e).__name__})."
            for n in hosted:
                e = known.get(n)
                out["providers"].append({"id": n, "icon": PROVIDER_ICONS.get(n, "◆"), "where": "hermes",
                                         "listed": e is not None, "set": bool(e and e.get("has_key")),
                                         "models": (e or {}).get("models") or []})
            return 200, out
        ks = self.lab.keys
        for n in hosted:
            st = ks.status(n) if hasattr(ks, "status") else {"set": False, "source": "none"}
            out["providers"].append({"id": n, "icon": PROVIDER_ICONS.get(n, "◆"), "where": "lab", "env": ENV_NAMES[n], **st})
        out["store"] = {"keyring": _keyring_ok(), "file": str(ks.env_file) if hasattr(ks, "env_file") else ""}
        return 200, out

    def keys_set(self, b: dict) -> tuple[int, dict]:
        if self.cfg["mode"] == "connected":
            return 409, {"ok": False, "code": "hermes_holds_keys", "message": "In connected mode Hermes holds the keys. Add it in Hermes → Settings → API keys."}
        name = str(b.get("provider") or "")
        try:
            where = self.lab.keys.set(name, str(b.get("key") or ""))
        except KeyMissing as e:
            return 400, {"ok": False, "code": "bad_key", "message": str(e)}
        try:
            self.lab.models.forget(name)                           # a new key must not serve the old key's cached list
        except Exception:                                          # noqa: BLE001
            pass
        return 200, {"ok": True, "provider": name, "source": where}

    def keys_remove(self, b: dict) -> tuple[int, dict]:
        if self.cfg["mode"] == "connected":
            return 409, {"ok": False, "code": "hermes_holds_keys", "message": "In connected mode Hermes holds the keys."}
        name = str(b.get("provider") or "")
        return 200, {"ok": True, "provider": name, "removed": self.lab.keys.remove(name)}

    def keys_test(self, b: dict) -> tuple[int, dict]:
        """Lists the provider's models with the stored key — the only thing a key is ever used for here."""
        if not self.cfg["flags"]["router"]:
            return _off("router")
        name = str(b.get("provider") or "")
        try:
            self.lab.models.forget(name)                           # list afresh — a stale cache would hide a bad key
        except Exception:                                          # noqa: BLE001
            pass
        r = self.lab.list_models(name, {})
        n = len(r.get("models") or [])
        return 200, {"ok": True, "provider": name, "models": n, "source": r.get("source")}

    # ---- 🧠 memory (flag `memory`, 2026-11-24 M1) ----
    def memory_get(self, q: dict) -> tuple[int, dict]:
        if not self.cfg["flags"].get("memory"):
            return _off("memory")
        name, qq = (q.get("name") or [""])[0], (q.get("q") or [None])[0]
        if name:
            return 200, {"ok": True, "subject": memory.read(name)}
        if qq is not None:
            return 200, {"ok": True, "hits": memory.search(qq)}
        return 200, {"ok": True, "subjects": memory.subjects(),
                     "sources": [{"name": n, "file": str(f)} for n, _, f in memory.import_sources()]}

    def memory_post(self, op: str, b: dict) -> tuple[int, dict]:
        if not self.cfg["flags"].get("memory"):
            return _off("memory")
        if op == "import":
            return 200, {"ok": True, "report": memory.import_all()}
        if op == "add":                                   # typed by Scott on the Memory page → his own line
            return 200, {"ok": True, **memory.add_fact(str(b.get("name") or "notes"), str(b.get("text") or ""), "scott")}
        if op == "save":
            lines = b.get("lines") if isinstance(b.get("lines"), list) else []
            return 200, {"ok": True, "subject": memory.write_subject(str(b.get("name") or ""), str(b.get("description") or ""),
                                                                    [l for l in lines if isinstance(l, dict)], "edit")}
        if op == "undo" and isinstance(b.get("ids"), list):   # ↶ exactly one review's writes (2026-11-24)
            return 200, {"ok": True, **memory.undo_ids(b["ids"])}
        if op == "undo":                                  # count > 1 = undo a whole review apply
            n, last = max(1, min(int(b.get("count") or 1), 200)), {}
            for _ in range(n):
                last = memory.undo_last()
            return 200, {"ok": True, **last, "count": n}
        if op == "review":                                # ⬇ the review .md
            names = b.get("names") if isinstance(b.get("names"), list) else None
            return 200, {"ok": True, "md": memory.review_md(names), "file": f"memory-review-{time.strftime('%Y-%m-%d')}.md"}
        if op == "answers":                               # ⬆ answers .md → before/after only, nothing written
            return 200, {"ok": True, **memory.preview_answers(str(b.get("md") or "")[:500_000])}
        if op == "apply":                                 # ✅ the ticked changes
            ids = b.get("ids") if isinstance(b.get("ids"), list) else None
            return 200, {"ok": True, **memory.apply_answers(str(b.get("md") or "")[:500_000], ids)}
        if op == "questions":                             # 🎙️ for a voice review
            return 200, {"ok": True, "questions": memory.questions()}
        return 404, {"ok": False, "code": "not_found"}

    # ---- 📝 prompt builder (flag `prompt`, 2026-11-24 M4) ----
    def _repo(self, name: str):
        r = repos.linked(self.cfg)
        return (name, r[name]) if name in r else ("", None)

    def prompt_get(self, q: dict) -> tuple[int, dict]:
        if not self.cfg["flags"].get("prompt"):
            return _off("prompt")
        return 200, {"ok": True, "prompts": promptbuilder.listing(), "repos": sorted(repos.linked(self.cfg)),
                     "agent_on": bool(self.cfg["flags"].get("agent")), "writer": self.cfg.get("prompt_writer") or []}

    def prompt_post(self, op: str, b: dict) -> tuple[int, dict]:
        if not self.cfg["flags"].get("prompt"):
            return _off("prompt")
        idea = str(b.get("idea") or "")[:4000]
        rname, rpath = self._repo(str(b.get("repo") or ""))
        proj = store.project(self._pid(b.get("project"))) or {"id": "scratch", "name": "Scratch"}
        if op == "plain":                                 # no model, no cost
            return 200, {"ok": True, "md": promptbuilder.plain(idea, f"~/{rname}" if rname else "~/"),
                         **promptbuilder.size_hint(idea)}
        if op == "draft":
            if not self.cfg["flags"].get("router"):
                return _off("router")
            d = promptbuilder.draft(self.lab, proj, str(b.get("provider") or ""), str(b.get("model") or ""), idea, rname, rpath,
                                    backups=[] if b.get("no_backup") else
                                    [self.cfg.get("prompt_writer") or []] + list(self.cfg.get("prompt_writer_backups") or []))
            return 200, {"ok": True, **d, "spend": self.spend()}
        md = str(b.get("md") or "")[:promptbuilder.MAX_PROMPT]
        if op == "save":
            return 200, {"ok": True, "file": str(promptbuilder.save(md, str(b.get("name") or "")))}
        if op == "send":
            target, f = str(b.get("target") or ""), promptbuilder.save(md, str(b.get("name") or ""))
            if target == "lab":
                if not self.cfg["flags"].get("agent"):
                    return _off("agent")
                task = ("Follow this build prompt. Do Module 0 first and stop at its gate.\n\n" + md)[:4000]
                # 2026-11-24: the 🧩 chips go along (🖼 → a picture, not an audit) and the robot still tests pages
                run = self.agents.start(self.lab, self.cfg, proj, str(b.get("provider") or ""), str(b.get("model") or ""), task,
                                        selftest=self._play_test,
                                        ctypes=b.get("ctypes") if isinstance(b.get("ctypes"), list) else [])
                return 200, {"ok": True, "file": str(f), "run": run.view()}
            if target == "claude":
                q = promptbuilder.queue_for_claude(f, rname or "hermes", str(rpath or Path.home() / "hermes"))
                return 200, {"ok": True, "file": str(f), **q}
            return 400, {"ok": False, "code": "bad_args", "message": "Pick 🤖 Lab agent or ✳️ Claude."}
        return 404, {"ok": False, "code": "not_found"}

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

    def where_get(self, q: dict) -> tuple[int, dict]:
        """📍 the real folders behind a project (2026-11-24)."""
        return 200, {"ok": True, **preview.where(self._pid(q.get("project")))}

    def where_open(self, b: dict) -> tuple[int, dict]:
        """📂 Open a project folder (or its pictures/ docs/ / the Gallery) in the file manager on gandalf."""
        w = preview.where(self._pid(b.get("project")))
        which = str(b.get("which") or "folder")
        if which not in ("folder", "pictures", "docs", "gallery"):
            return 400, {"ok": False, "code": "bad_args", "icon": "❓", "message": "Unknown folder."}
        path = Path(w[which])
        path.mkdir(parents=True, exist_ok=True)
        if not shutil.which("xdg-open"):
            return 200, {"ok": True, "opened": False, "path": str(path), "message": "No file manager here — 📋 copy the path instead."}
        subprocess.Popen(["xdg-open", str(path)], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True)
        return 200, {"ok": True, "opened": True, "path": str(path),
                     "message": "📂 Opened on gandalf's screen. On your phone, 📋 copy the path instead."}

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
            try:                                                   # 2026-11-24: runs saved before a restart come back
                self._agents.restore(self.lab, self.cfg, self._play_test)
            except Exception:                                      # noqa: BLE001 — never block the Lab starting
                pass
        return self._agents

    def agent_start(self, b: dict) -> tuple[int, dict]:
        if not self.cfg["flags"]["agent"]:
            return _off("agent")
        proj = store.project(self._pid(b.get("project")))
        # 🪞 Show & change runs get their own, larger step cap (2026-11-24: 12 capped both pilot lanes on a 1-spot edit)
        cap = int(self.cfg.get("live_step_cap", 60)) if b.get("kind") == "live" else None
        live = b.get("kind") == "live"          # 🪞 runs: Scott already pointed at the spot, and that flow has its own robot
        ctypes = [] if live else (b.get("ctypes") if isinstance(b.get("ctypes"), list) else [])
        bt = None if live else self._batch_req(b, ctypes)       # 🎛 Batch create (2026-11-24 Module 3)
        if isinstance(bt, tuple):
            return bt
        run = self.agents.start(self.lab, self.cfg, proj, str(b.get("provider") or ""), str(b.get("model") or ""),
                                str(b.get("task") or ""), step_cap=cap, ask_first=bool(b.get("ask_first")) and not live,
                                selftest=None if live else self._play_test, ctypes=ctypes, batch=bt)
        return 200, {"ok": True, "run": run.view()}

    def _batch_req(self, b: dict, ctypes: list):
        """🎛 The batch part of a start: cleaned, cost-checked against today's cap, ➕ Make more carries the earlier
        results. None = an ordinary run · (status, body) = refused before anything is spent."""
        from . import batch as B
        req = b.get("batch")
        if not isinstance(req, dict) or not B.norm(req, ctypes):
            return None
        req = dict(req)
        kind = B.kind_for(ctypes)
        est = B.estimate(kind, max(1, min(B.MAX_N, int(req.get("n") or 1))), self.cfg, self.spend()["today_usd"] or 0.0)
        if not est["fits"]:
            return 200, {"ok": False, "code": "cap", "icon": "💲", "estimate": est,
                         "message": f"That batch is about ${est['est_usd']:.2f}, but only ${est['left_usd']:.2f} is left of today's "
                                    f"${est['cap_usd']:.2f} cap — make {est['max_n']} or fewer, or wait until tomorrow."}
        prev = str(req.get("from_run") or "")
        req["earlier"] = []
        if prev:                                                   # ➕ Make more: same series, the grid keeps the earlier ones
            try:
                pv = self.agents.get(prev).view().get("batch") or {}
                req["earlier"] = (pv.get("earlier") or []) + (pv.get("items") or [])
                req["start"] = int(pv.get("next_start") or req.get("start") or 0)
            except KeyError:
                pass
        return req

    def batch_estimate(self, b: dict) -> tuple[int, dict]:
        """🎛 What a batch would cost, before it runs. Spends nothing."""
        from . import batch as B
        ctypes = b.get("ctypes") if isinstance(b.get("ctypes"), list) else []
        kind = B.kind_for(ctypes)
        if not kind:
            return 200, {"ok": True, "kind": "", "message": "🎛 Batch works for 🖼 pictures and 📝 docs (video later)."}
        try:
            n = max(1, min(B.MAX_N, int(b.get("n") or 1)))
        except (TypeError, ValueError):
            n = 1
        return 200, {"ok": True, **B.estimate(kind, n, self.cfg, self.spend()["today_usd"] or 0.0)}

    def batch_keep(self, b: dict) -> tuple[int, dict]:
        """⭐ Keep / un-keep one batch result (kept.json in the project folder)."""
        from . import batch as B
        proj = store.project(self._pid(b.get("project")))
        try:
            kept = B.set_kept(preview.ensure_site(proj["id"]).resolve(), str(b.get("path") or ""), bool(b.get("keep")))
        except ValueError as e:
            return 400, {"ok": False, "code": "bad_args", "icon": "⭐", "message": str(e)}
        return 200, {"ok": True, "kept": kept}

    def _play_test(self, run) -> dict | None:
        """🤖 Robot play-test of the project page when a run finishes (2026-11-24). None = no page to test."""
        if not self.cfg["flags"].get("preview") or not (run.root / "index.html").is_file():
            return None
        port = getattr(self, "bind_port", 0)
        if not port:
            return None
        host = getattr(self, "bind_host", "127.0.0.1")
        host = "127.0.0.1" if host in ("", "0.0.0.0", "::") else host
        return robotcheck.play(f"http://{host}:{port}/preview/{run.project['id']}/",
                               run.log.parent / "shots" / run.id, self.cfg,
                               mode=creation.robot_mode(getattr(run, "ctypes", [])))

    REPHRASE_SYS = ("Scott wants to change something the AI Lab just made. Rewrite his rough words as ONE clear, specific "
                    "change request (1-3 short sentences) that an AI builder can follow. Keep everything he asked for, "
                    "add nothing he didn't ask for, use plain words, no lists, no quotes. Reply with the request only.")

    def agent_rephrase(self, b: dict) -> tuple[int, dict]:
        """🪄 Help me say it: rough words → a clear change request Scott can edit before it runs."""
        if not self.cfg["flags"]["agent"]:
            return _off("agent")
        text = str(b.get("text") or "").strip()[:1500]
        if not text:
            return 400, {"ok": False, "code": "bad_args", "icon": "✏️", "message": "Type what you want changed first."}
        proj = store.project(self._pid(b.get("project")))
        made = ", ".join(str(x)[:80] for x in (b.get("made") or [])[:8] if isinstance(x, str))
        ctx = f"What was made: {made}.\n" if made else ""
        from . import picture
        msgs = [{"role": "system", "content": self.REPHRASE_SYS}, {"role": "user", "content": ctx + "His words: " + text}]
        usd, why = 0.0, ""
        for prov, model in self._rephrase_writers(b):            # 2026-11-24 live: "⏳ is not a valid model ID" (HTTP 400)
            try:
                r = self.lab.chat(proj, prov, model, msgs, 300, cap_usd=0.05, task="lab-rephrase")
            except Exception as e:                               # noqa: BLE001 — try the next writer
                why = f"{model}: {str(e)[:120]}"
                continue
            usd += float(r.usd or 0)
            out = (r.text or "").strip().strip('"').strip()
            if out and len(out) <= 1200 and not picture.REFUSAL_RX.search(out[:80]):
                return 200, {"ok": True, "text": out, "usd": round(usd, 6), "writer": f"{prov}/{model}"}
            why = f"{model} didn't give a usable rewrite"
        return 200, {"ok": False, "code": "no_writer", "icon": "🪄",
                     "message": f"No writer could help ({why or 'none set up'}) — your own words work too.", "usd": round(usd, 6)}

    @staticmethod
    def _real_model(m: str) -> bool:
        """A model id, not a list placeholder like ⏳ (the select box before its models load)."""
        return bool(re.fullmatch(r"[A-Za-z0-9][\w.:/@+-]*", m or ""))

    def _rephrase_writers(self, b: dict) -> list[tuple[str, str]]:
        """🪄 writers in order: picture changes → the uncensored picture writers first (a mainstream writer refuses
        body words); otherwise the pane's own model, then the prompt writer and its backups. Placeholders skipped."""
        from . import picture
        prov, model = str(b.get("provider") or ""), str(b.get("model") or "")
        mine = [(prov, model)] if prov and self._real_model(model) else []
        pw = [tuple(w) for w in [self.cfg.get("prompt_writer") or []] + list(self.cfg.get("prompt_writer_backups") or [])
              if isinstance(w, (list, tuple)) and len(w) == 2]
        if b.get("picture"):
            pics = [tuple(w) for w in (self.cfg.get("picture_writers") or []) if isinstance(w, (list, tuple)) and len(w) == 2]
            order = (pics or list(picture.WRITERS)) + mine + pw
        else:
            order = mine + pw
        have = getattr(self.lab, "providers", None)
        out: list[tuple[str, str]] = []
        for w in order:
            if w not in out and self._real_model(w[1]) and (have is None or w[0] in have):
                out.append(w)
        return out

    def agent_more(self, b: dict) -> tuple[int, dict]:
        """▶ Continue a run that hit its step limit."""
        if not self.cfg["flags"]["agent"]:
            return _off("agent")
        return 200, {"ok": True, "run": self.agents.more(str(b.get("id") or "")).view()}

    def agent_resume(self, b: dict) -> tuple[int, dict]:
        """▶ Resume a run a Lab restart caught mid-step (2026-11-24)."""
        if not self.cfg["flags"]["agent"]:
            return _off("agent")
        return 200, {"ok": True, "run": self.agents.resume(str(b.get("id") or "")).view()}

    def agent_shot(self, rid: str, name: str) -> bytes | None:
        """A robot screenshot of one run (png)."""
        if not self.cfg["flags"]["agent"] or not re.fullmatch(r"[a-z]{1,20}\.png", name or ""):
            return None
        try:
            r = self.agents.get(rid)
        except KeyError:
            return None
        f = r.log.parent / "shots" / r.id / name
        return f.read_bytes() if f.is_file() else None

    def agent_run(self, q: dict) -> tuple[int, dict]:
        if not self.cfg["flags"]["agent"]:
            return _off("agent")
        return 200, {"ok": True, "run": self.agents.get((q.get("id") or [""])[0]).view(), "spend": self.spend()}

    def agent_live(self, q: dict) -> tuple[int, dict]:
        """🏃 Runs working on a project now — art runs can run side by side (2026-11-24)."""
        if not self.cfg["flags"]["agent"]:
            return _off("agent")
        pid = self._pid((q.get("project") or [""])[0])
        return 200, {"ok": True, "runs": self.agents.live(pid)}

    def agent_answer(self, b: dict) -> tuple[int, dict]:
        """M5: Scott's answer to the agent's on-screen question."""
        if not self.cfg["flags"]["agent"]:
            return _off("agent")
        return 200, {"ok": True, "run": self.agents.answer(str(b.get("id") or ""), str(b.get("answer") or "")).view()}

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

    # ---- 🪞 Show & change (flag `live`, 2026-11-23): a running app's page, Now beside New ----
    @property
    def live(self):
        if getattr(self, "_live", None) is None:
            self._live = livepage.Live(self.cfg, getattr(self, "bind_host", "127.0.0.1"))
        return self._live

    def _live_view(self, pid: str, app: dict) -> dict:
        return {"changed": livepage.changed(pid, app), "writes": self.live.allow_writes, "blocked": self.live.blocked}

    def live_apps(self, q: dict) -> tuple[int, dict]:
        if not self.cfg["flags"]["live"]:
            return _off("live")
        found = livepage.apps(self.cfg)
        return 200, {"ok": True, "ports": self.live.ports(), "apps": [
            {"name": n, "repo": a["repo"], "web": a["web"], "up": livepage.is_up(a), "pages": livepage.pages(a)}
            for n, a in found.items()]}

    def live_open(self, b: dict) -> tuple[int, dict]:
        if not self.cfg["flags"]["live"]:
            return _off("live")
        pid, app = self._pid(b.get("project")), livepage.app_of(self.cfg, str(b.get("app") or ""))
        return 200, {"ok": True, "ports": self.live.open(pid, app["name"]), **self._live_view(pid, app)}

    def live_changed(self, q: dict) -> tuple[int, dict]:
        if not self.cfg["flags"]["live"]:
            return _off("live")
        pid, app = self._pid(q.get("project")), livepage.app_of(self.cfg, (q.get("app") or [""])[0])
        return 200, {"ok": True, **self._live_view(pid, app)}

    def live_writes(self, b: dict) -> tuple[int, dict]:
        if not self.cfg["flags"]["live"]:
            return _off("live")
        self.live.allow_writes = bool(b.get("allow"))
        return 200, {"ok": True, "writes": self.live.allow_writes}

    def live_check(self, b: dict) -> tuple[int, dict]:
        if not self.cfg["flags"]["live"]:
            return _off("live")
        pid, app = self._pid(b.get("project")), livepage.app_of(self.cfg, str(b.get("app") or ""))
        path = str(b.get("path") or "/")
        if not path.startswith("/") or len(path) > 500 or any(c in path for c in "\r\n "):
            path = "/"
        return 200, {"ok": True, "now": self.live.status_of("now", path), "new": self.live.status_of("new", path),
                     "syntax": livepage.syntax(pid, app), **self._live_view(pid, app)}

    def live_robot(self, b: dict) -> tuple[int, dict]:
        """Fix 4: a headless browser tests the spot Scott asked about, Now vs New. Green needs this."""
        if not self.cfg["flags"]["live"]:
            return _off("live")
        pid, app = self._pid(b.get("project")), livepage.app_of(self.cfg, str(b.get("app") or ""))
        if self.live.target != {"pid": pid, "app": app["name"]}:
            return 409, {"ok": False, "message": "Open the page in 🪞 Show & change first.", "code": "not_open", "icon": "🪞"}
        path = str(b.get("path") or "/")
        if not path.startswith("/") or len(path) > 500 or any(c in path for c in "\r\n "):
            path = "/"
        ports, host = self.live.ports(), "127.0.0.1"
        res = robotcheck.run(f"http://{host}:{ports['now']}{path}", f"http://{host}:{ports['new']}{path}",
                             str(b.get("selector") or ""), config.home() / "projects" / pid / "live" / "robot", self.cfg)
        return 200, {"ok": True, "robot": res}

    def live_keep(self, b: dict) -> tuple[int, dict]:
        if not self.cfg["flags"]["live"]:
            return _off("live")
        pid, app = self._pid(b.get("project")), livepage.app_of(self.cfg, str(b.get("app") or ""))
        return 200, {"ok": True, **livepage.keep(pid, app, str(b.get("note") or ""))}

    def live_discard(self, b: dict) -> tuple[int, dict]:
        if not self.cfg["flags"]["live"]:
            return _off("live")
        pid, app = self._pid(b.get("project")), livepage.app_of(self.cfg, str(b.get("app") or ""))
        return 200, {"ok": True, **livepage.discard(pid, app)}

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

    # ---- 📦 Make it an app (lab-ship M3, 2026-11-24): Hermes app_ship → 🧪 test builds. Spends nothing. ----
    def ship_options(self, q: dict) -> tuple[int, dict]:
        pid = self._pid((q.get("project") or [""])[0])
        return 200, {"ok": True, "mode": self.cfg["mode"], "options": ship.options(pid)}

    def ship_start(self, b: dict) -> tuple[int, dict]:
        plats = b.get("platforms") if isinstance(b.get("platforms"), list) else None
        return 200, ship.start(self.lab, self.cfg, self._pid(b.get("project")), str(b.get("name") or ""),
                               str(b.get("folder") or ""), plats, str(b.get("orientation") or "any"))

    def ship_wait(self, b: dict) -> tuple[int, dict]:
        return 200, ship.wait(self.lab, self.cfg, str(b.get("key") or ""))

    def review_apply(self, b: dict) -> tuple[int, dict]:
        return 200, review.apply(str(b.get("id") or ""), str(b.get("sha") or ""), str(b.get("confirm") or ""))

    def review_apply_group(self, b: dict) -> tuple[int, dict]:
        return 200, review.apply_group(list(b.get("items") or []), str(b.get("confirm") or ""))

    def guard_state(self, q: dict) -> tuple[int, dict]:
        s = guardlink.state(self.cfg)
        return 200, {**s, "public_url": self.cfg.get("guard_public_url") or ""}

    def review_reject(self, b: dict) -> tuple[int, dict]:
        return 200, review.reject(str(b.get("id") or ""))

    def chat(self, b: dict) -> tuple[int, dict]:
        if not self.cfg["flags"]["router"]:
            return _off("router")
        proj = store.project(str(b.get("project") or "")) or {"id": "scratch", "name": "Scratch"}
        msgs = b.get("messages")
        if not isinstance(msgs, list) or not msgs:
            return 400, {"ok": False, "code": "bad_args", "message": "Nothing to send."}
        used, saved = [], []
        if self.cfg["flags"].get("memory"):                        # 🧠 M2: what the Lab knows + save what he states
            last = next((str(m.get("content") or "") for m in reversed(msgs) if isinstance(m, dict) and m.get("role") == "user"), "")
            try:
                saved = memory.learn(last, "Ask models")
                mem, used = memory.for_context(proj.get("name", ""), last, budget_chars=3000)
                if mem:
                    msgs = [{"role": "system", "content": mem}] + [m for m in msgs if isinstance(m, dict)]
            except Exception:                                     # noqa: BLE001 — memory never blocks a chat
                pass
        r = self.lab.chat(proj, str(b.get("provider") or ""), str(b.get("model") or ""), msgs,
                          int(b.get("max_tokens") or 1024), task=f"lab:{proj['id']}")
        return 200, {"ok": True, "text": r.text, "provider": r.provider, "model": r.model, "usd": r.usd,
                     "priced": r.priced, "tokens_in": r.tokens_in, "tokens_out": r.tokens_out, "spend": self.spend(),
                     "memory_used": used, "memory_saved": saved}


ERRORS = ((PrivacyRefused, 403, "privacy", "🔒"), (SpendBlocked, 402, "over_cap", "💲"),
          (KeyMissing, 400, "no_key", "🔑"), (HermesRefused, 502, "hermes", "🔌"),
          (HttpError, 502, "provider", "🌐"), (KeyError, 400, "bad_args", "❓"), (ValueError, 400, "bad_args", "❓"))


def make_server(app: App, host: str = "127.0.0.1", port: int = 0) -> ThreadingHTTPServer:
    app.bind_host = host                        # 🪞 the preview ports listen where the Lab does
    def index() -> bytes:                       # 2026-11-23: read per load — page edits show without a Lab restart
        return (WEB / "index.html").read_bytes()

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
            frames = ""
            if not csp and app.cfg["flags"].get("live"):
                hn = (self.headers.get("Host") or "").rsplit(":", 1)[0]
                if re.fullmatch(r"[A-Za-z0-9.-]{1,253}", hn):
                    frames = "; frame-src 'self' " + " ".join(f"{sch}://{hn}:{pt}" for pt in app.live.ports().values()
                                                              for sch in ("http", "https"))
            self.send_header("Content-Security-Policy", csp or
                             "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; "
                             "img-src 'self' data:; connect-src 'self'; frame-ancestors 'self'" + frames)
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
            except livepage.LiveError as e:
                code = {"not_found": 404, "port_busy": 409}.get(e.code, 400)
                body = {"ok": False, "code": e.code, "icon": e.icon, "message": e.message[:400]}
            except memory.MemError as e:
                code = {"not_found": 404, "nothing": 409}.get(e.code, 400)
                body = {"ok": False, "code": e.code, "icon": "🧠", "message": e.message[:400]}
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
                if rel.lower().endswith(MEDIA_EXT):          # 🎬 stream video/audio (any length, seekable)
                    return self._stream(pid, rel)
                code, ctype, data = app.pv.get(pid, rel)
                if code == 413:                             # too big for one piece → stream it instead
                    return self._stream(pid, rel)
            except preview.PreviewError as e:
                code, ctype, data = 503, "text/plain; charset=utf-8", f"{e.icon} {e.message}".encode()
            return self._send(code, data, ctype, csp=PREVIEW_CSP)

        def _stream(self, pid: str, rel: str):
            """🎬 HTTP Range over the sandbox's slice reader: 206 for a range, 200 streamed in slices otherwise."""
            st = app.pv.stat(pid, rel)
            if not st.get("ok"):
                return self._send(int(st.get("status") or 404), b"Not found in this project.", "text/plain; charset=utf-8",
                                  csp=PREVIEW_CSP)
            size, ctype = int(st["size"]), st["ctype"]
            rng = parse_range(self.headers.get("Range"), size)
            if rng == "bad":
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{size}")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return None
            start, end = rng if rng else (0, size - 1)
            self.send_response(206 if rng else 200)
            self.send_header("Content-Type", ctype)
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Length", str(max(0, end - start + 1)))
            if rng:
                self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", PREVIEW_CSP)
            self.end_headers()
            pos = start
            try:
                while pos <= end:
                    data = app.pv.slice(pid, rel, pos, min(4_000_000, end - pos + 1))
                    if not data:
                        break
                    self.wfile.write(data)
                    pos += len(data)
            except (BrokenPipeError, ConnectionResetError):   # the player seeked away — normal
                pass
            except preview.PreviewError:
                pass                                          # headers are out; the player retries the range
            return None

        def _before_page(self, rest: str):
            """/preview-before/<pid>/<run id>/<rel> → the project page as it was when that run started (↔ Before)."""
            if not app.cfg["flags"]["preview"]:
                return self._send(403, b"Live preview is not switched on yet.", "text/plain; charset=utf-8")
            parts = rest.split("/", 2)
            try:
                pid, rid = app._pid(parts[0]), parts[1] if len(parts) > 1 else ""
                root = config.home() / "projects" / pid / "agent" / "before" / rid
                if not re.fullmatch(r"[0-9a-f]{10}", rid) or not root.is_dir():
                    return self._send(404, b"No Before copy for this run.", "text/plain; charset=utf-8")
                code, ctype, data = app.pv.get(f"{pid}--b{rid}", parts[2] if len(parts) > 2 else "", root)
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
            if u.path.startswith("/preview-before/"):
                return self._before_page(u.path[len("/preview-before/"):])
            if u.path.startswith("/compare-page/"):
                return self._compare_page(u.path[len("/compare-page/"):])
            if u.path.startswith("/api/") and self._foreign():
                return self._send(403, {"ok": False, "code": "cross_origin"})
            if u.path in ("/", "/index.html"):
                return self._send(200, index(), "text/html; charset=utf-8")
            if u.path == "/icon.svg":
                return self._send(200, (WEB / "icon.svg").read_bytes(), "image/svg+xml")
            if u.path == "/api/state":
                return self._run(lambda: (200, app.state()))
            if u.path == "/api/models":
                return self._run(app.models, q)
            if u.path == "/api/keys":
                return self._run(app.keys, q)
            if u.path == "/api/prompt":
                return self._run(app.prompt_get, q)
            if u.path == "/api/memory":
                return self._run(app.memory_get, q)
            if u.path == "/api/video_paths":               # 🛤 ⚙️ video paths: switch on/off + ⭐ default (2026-11-24)
                return self._run(lambda: (200, {"ok": True, "paths": videomod.all_paths(), "kinds": videomod.KINDS}))
            if u.path == "/api/picture_first":             # 🏠/🌐 picture route (local pictures M3, 2026-11-24)
                from . import picture_route                # noqa: PLC0415
                return self._run(lambda: (200, {"ok": True, "first": picture_route.first(),
                                                "cfg": str(app.cfg.get("picture_first") or ""),
                                                "speed": picture_route.speed(),
                                                "cfg_speed": str(app.cfg.get("picture_speed") or "")}))
            if u.path == "/api/creation_types":            # 🧩 chips above the task box (2026-11-24)
                return self._run(lambda: (200, {"ok": True, "types": creation.public()}))
            if u.path == "/api/looks":                     # 🎨 picture Looks catalog + saved + last (2026-11-24)
                return self._run(lambda: (200, looks.public()))
            if u.path == "/api/roster":
                return self._run(app.roster, q)
            if u.path == "/api/where":                     # 📍 where a project's files really are (2026-11-24)
                return self._run(app.where_get, q)
            if u.path == "/api/preview/files":
                return self._run(app.preview_files, q)
            if u.path == "/api/preview/file":
                return self._run(app.preview_read, q)
            if u.path == "/api/preview/version":
                return self._run(app.preview_version, q)
            if u.path == "/api/agent/live":
                return self._run(app.agent_live, q)
            if u.path == "/api/agent/run":
                return self._run(app.agent_run, q)
            if u.path == "/api/live/apps":
                return self._run(app.live_apps, q)
            if u.path == "/api/live/changed":
                return self._run(app.live_changed, q)
            if u.path == "/api/review":
                return self._run(app.review_list, q)
            if u.path == "/api/ship/options":
                return self._run(app.ship_options, q)
            if u.path == "/api/compare":
                return self._run(app.compare_get, q)
            if u.path == "/api/health":                          # 🛡 the Guard watches this
                return self._run(lambda: (200, {"ok": True, "app": "ailab", "pid": os.getpid(), "started": _STARTED}))
            if u.path == "/api/guard":
                return self._run(app.guard_state, q)
            if u.path == "/api/agent/approvals":
                return self._run(app.agent_approvals, q)
            if u.path == "/api/agent/shot":
                png = app.agent_shot((q.get("id") or [""])[0], (q.get("name") or [""])[0])
                return self._send(200, png, "image/png") if png else self._send(404, b"No such picture.", "text/plain; charset=utf-8")
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
            if p == "/api/keys/set":
                return self._run(app.keys_set, b)
            if p == "/api/keys/remove":
                return self._run(app.keys_remove, b)
            if p == "/api/keys/test":
                return self._run(app.keys_test, b)
            if p == "/api/chat":
                return self._run(app.chat, b)
            if p == "/api/preview/file":
                return self._run(app.preview_save, b)
            if p == "/api/preview/capture":
                return self._run(app.preview_capture, b)
            if p in LIVE_POST:
                return self._run(getattr(app, LIVE_POST[p]), b)
            if p == "/api/video_paths":                    # 🛤 ⚙️ {"id","on"} or {"star": id}
                return self._run(lambda: (200, videomod.set_path(b)))
            if p == "/api/picture_first":                  # 🏠/🌐 {"first": "local"|"venice"}
                from . import picture_route                # noqa: PLC0415
                r = (picture_route.set_speed(str(b.get("speed") or "")) if "speed" in b    # ⚡/🎨 {"speed"} (2026-11-25)
                     else picture_route.set_first(str(b.get("first") or "")))
                if r["ok"]:
                    r["cfg"] = str(app.cfg.get("picture_first") or "")
                    r["cfg_speed"] = str(app.cfg.get("picture_speed") or "")
                return self._run(lambda: (200 if r["ok"] else 400, r))
            if p == "/api/agent/start":
                return self._run(app.agent_start, b)
            if p == "/api/where/open":
                return self._run(app.where_open, b)
            if p == "/api/batch/estimate":                 # 🎛 Batch create (2026-11-24)
                return self._run(app.batch_estimate, b)
            if p == "/api/batch/keep":
                return self._run(app.batch_keep, b)
            if p == "/api/agent/rephrase":
                return self._run(app.agent_rephrase, b)
            if p == "/api/agent/more":
                return self._run(app.agent_more, b)
            if p == "/api/agent/resume":
                return self._run(app.agent_resume, b)
            if p == "/api/agent/answer":
                return self._run(app.agent_answer, b)
            if p == "/api/agent/stop":
                return self._run(app.agent_stop, b)
            if p == "/api/agent/undo":
                return self._run(app.agent_undo, b)
            if p.startswith("/api/prompt/"):
                return self._run(app.prompt_post, p[len("/api/prompt/"):], b)
            if p.startswith("/api/memory/"):
                return self._run(app.memory_post, p[len("/api/memory/"):], b)
            if p == "/api/compare/start":
                return self._run(app.compare_start, b)
            if p == "/api/compare/stop":
                return self._run(app.compare_stop, b)
            if p == "/api/compare/capture":
                return self._run(app.compare_capture, b)
            if p == "/api/compare/review":
                return self._run(app.compare_review, b)
            if p == "/api/ship/start":
                return self._run(app.ship_start, b)
            if p == "/api/ship/wait":
                return self._run(app.ship_wait, b)
            if p == "/api/review/send":
                return self._run(app.review_send, b)
            if p == "/api/review/apply":
                return self._run(app.review_apply, b)
            if p == "/api/review/apply_group":
                return self._run(app.review_apply_group, b)
            if p == "/api/review/reject":
                return self._run(app.review_reject, b)
            if p == "/api/looks/save":
                return self._run(lambda: (200, looks.save(b.get("name"), b.get("look") if isinstance(b.get("look"), list) else [])))
            if p == "/api/looks/delete":
                return self._run(lambda: (200, looks.delete(str(b.get("name") or ""))))
            if p == "/api/autosave":
                return self._run(lambda: (200, store.autosave(str(b.get("project")), str(b.get("field") or "draft"),
                                                              str(b.get("text") or ""))))
            if p == "/api/projects":
                return self._run(lambda: (200, {"ok": True, "project": store.save_project(
                    str(b.get("name") or ""), bool(b.get("sensitive")))}))
            return self._send(404, {"ok": False, "code": "not_found"})

    httpd = ThreadingHTTPServer((host, port), H)
    app.bind_port = httpd.server_address[1]     # 🤖 the play-test robot opens the Lab's own preview page
    return httpd


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
    notify.Watcher(app.agents, app.cfg).start()          # 📱 M5: phone pings — only "finished" or "stuck"
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        if getattr(app, "_agents", None):
            app._agents.stop_all()
        if getattr(app, "_cmps", None):
            app._cmps.stop_all()
        if getattr(app, "_live", None):
            app._live.close()
        if getattr(app, "_pv", None):
            app._pv.close()                                         # stop sandboxed preview servers
    return 0

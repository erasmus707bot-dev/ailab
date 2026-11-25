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
from . import gate
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
       "live": "🪞 Show & change", "memory": "🧠 Memory", "prompt": "📝 Prompt builder", "craft": "📓 Craft Book"}
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

    # ---- 📓 Craft Book (flag `craft`, 2026-11-25): what makes the work come out right, learned from results ----
    def craft_get(self, q: dict) -> tuple[int, dict]:
        from . import craft
        if not self.cfg["flags"].get("craft"):
            return _off("craft")
        if (q.get("review") or [""])[0]:
            return 200, {"ok": True, "md": craft.review_md()}
        return 200, {"ok": True, **craft.view(), "settings": craft.settings(self.cfg)}

    def craft_post(self, op: str, b: dict) -> tuple[int, dict]:
        from . import craft
        if not self.cfg["flags"].get("craft"):
            return _off("craft")
        ids = [str(x) for x in (b.get("ids") or [])][:400]
        if op in ("live", "retired", "proposed"):
            return 200, {"ok": True, **craft.set_status(ids, op), **craft.view()}
        if op == "add":                                   # typed by Scott → his own note, live at once
            r = craft.add({k: b.get(k) for k in ("kind", "when", "do", "why")}, "scott", "live")
            return 200, {"ok": bool(r.get("note")), **r, **craft.view()}
        if op == "edit":
            r = craft.edit(str(b.get("id") or ""), str(b.get("do") or ""), b.get("when"), str(b.get("why") or ""))
            return 200, {"ok": bool(r.get("saved")), **r, **craft.view()}
        if op == "undo":
            return 200, {"ok": True, **craft.undo_last(), **craft.view()}
        if op == "seed":
            return 200, {"ok": True, "report": craft.seed(), **craft.view()}
        if op == "handoffs":
            return 200, {"ok": True, "report": craft.import_handoffs(), **craft.view()}
        if op == "review":
            return 200, {"ok": True, "report": craft.apply_review(str(b.get("text") or "")[:400_000]), **craft.view()}
        return 404, {"ok": False, "code": "not_found"}

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

    # 🗄 Shelf (remodel M2): ✅ Keep / 🗑 Throw away (hidden 30 days) / ↩ Bring back — ailab/shelf.py
    def _shelf_run(self, b: dict):
        r = self.agents.get(str(b.get("run") or ""))
        if r.state == "running":
            raise ValueError("It's still working — ⏹ Stop it or wait until it's done.")
        return r

    def shelf_get(self, q: dict) -> tuple[int, dict]:
        from . import shelf
        return 200, {"ok": True, **shelf.view(preview.ensure_site(self._pid(q.get("project"))))}

    def shelf_source(self, q: dict) -> tuple[int, dict]:
        """✏️ Change this (M3): the words a Library item was made from — newest run that made it, else its kept entry."""
        from . import shelf
        pid = self._pid(q.get("project"))
        path = str((q.get("path") or [""])[0])
        for r in sorted(list(self.agents.runs.values()), key=lambda x: getattr(x, "started", 0), reverse=True):
            try:
                if r.project["id"] == pid and any(m["path"] == path for m in r.made_view()):
                    return 200, {"ok": True, "task": r.task, "run": r.id}
            except Exception:                                    # noqa: BLE001 — an odd old run must not hide the rest
                continue
        for x in reversed(shelf.view(preview.ensure_site(pid))["kept"]):
            if path in (x.get("files") or []):
                return 200, {"ok": True, "task": x.get("task") or "", "run": x.get("run")}
        return 200, {"ok": True, "task": "", "run": None}

    # ---------- 🎭 M2 references ----------
    LOOP_CALLS = {"job": "get", "jobs": "jobs", "estimate": "estimate", "trust": "trust", "plan": "plan", "run": "run",
                  "rate": "rate", "spend_ok": "spend_ok", "author": "author"}

    def loop_call(self, name: str, arg: dict) -> tuple[int, dict]:
        """🔁 Creative Loop (Phase 3, 2026-11-25) — straight through to Hermes's creative_* tools."""
        from .loop import Loop, LoopError                           # noqa: PLC0415
        try:
            return 200, getattr(Loop(self), self.LOOP_CALLS[name])(arg)
        except LoopError as e:
            return e.status, {"ok": False, "code": e.code, "icon": "🔁", "message": str(e)[:400]}

    def refs_get(self, q: dict) -> tuple[int, dict]:
        from . import refs
        return 200, {"ok": True, "refs": refs.get(preview.ensure_site(self._pid(q.get("project")))), "max": refs.MAX_REFS}

    def refs_pin(self, b: dict) -> tuple[int, dict]:
        from . import refs
        return 200, refs.pin(preview.ensure_site(self._pid(b.get("project"))), str(b.get("path") or ""))

    def refs_unpin(self, b: dict) -> tuple[int, dict]:
        from . import refs
        return 200, refs.unpin(preview.ensure_site(self._pid(b.get("project"))), str(b.get("path") or ""))

    # ---------- 🎭 R1 global cast (Hermes store over MCP) ----------
    def _cast_mcp(self):
        mcp = getattr(self.lab, "mcp", None)
        if mcp is None:
            raise RuntimeError("🔌 The global cast lives in Hermes — switch the Lab to connected mode.")
        return mcp

    def _cast_do(self, fn) -> tuple[int, dict]:
        from .mcp_client import HermesRefused
        try:
            return 200, fn()
        except HermesRefused as e:
            return 200, {"ok": False, "icon": "🎭", "message": e.message + (f" — {e.fix}" if e.fix else "")}
        except RuntimeError as e:
            return 200, {"ok": False, "icon": "🔌", "message": str(e)}

    def story_get(self, q: dict) -> tuple[int, dict]:
        """📖 M3: the project's story bible, its chapters (shots, stills, film) and the start-card choices."""
        from . import story
        return 200, {"ok": True, **story.view(preview.ensure_site(self._pid(q.get("project"))).resolve())}

    def story_bible(self, b: dict) -> tuple[int, dict]:
        """📖 M3: save his edits to the story bible (title, tone, people, places, rules, facts)."""
        from . import story
        if not isinstance(b.get("bible"), dict):
            return 400, {"ok": False, "code": "bad_args", "icon": "📚", "message": "Send the bible to save."}
        root = preview.ensure_site(self._pid(b.get("project"))).resolve()
        return 200, {"ok": True, "bible": story.save_bible(root, b["bible"])}

    def cast_get(self, q: dict) -> tuple[int, dict]:
        """🎭 Every saved character + named casts (global), and the cast this project chose."""
        from . import cast
        root = preview.ensure_site(self._pid(q.get("project")))
        def go():
            lst = self._cast_mcp().call("cast_list", {})
            return {"ok": True, "characters": lst.get("characters", []), "casts": lst.get("casts", []),
                    "chosen": cast.chosen(root), "min": cast.MIN_N, "max": cast.MAX_N}
        return self._cast_do(go)

    def cast_choose(self, b: dict) -> tuple[int, dict]:
        """♻️ Reuse a cast in this project."""
        from . import cast
        pid = self._pid(b.get("project"))
        ids = b.get("ids") if isinstance(b.get("ids"), list) else []
        return self._cast_do(lambda: cast.pull(self._cast_mcp(), preview.ensure_site(pid), pid, str(b.get("name") or ""), ids))

    # ---------- ⭐ asset library M1: make a character from a result · 📇 Characters shelf (2026-11-25) ----------
    def _char(self, fn) -> tuple[int, dict]:
        from . import charcard
        try:
            return self._cast_do(fn)
        except charcard.CharError as e:
            return 200, {"ok": False, "icon": e.icon, "message": e.message}

    def cast_character(self, b: dict) -> tuple[int, dict]:
        from . import charcard
        pid = self._pid(b.get("project"))
        return self._char(lambda: charcard.make_from(self._cast_mcp(), preview.ensure_site(pid), pid, str(b.get("path") or ""),
                                                     b.get("name"), b.get("age"), b.get("brief"), b.get("use_here", True) is not False))

    def cast_use(self, b: dict) -> tuple[int, dict]:
        from . import charcard
        pid = self._pid(b.get("project"))
        return self._char(lambda: charcard.use(self._cast_mcp(), preview.ensure_site(pid), pid, str(b.get("id") or "")))

    def cast_leave(self, b: dict) -> tuple[int, dict]:
        from . import charcard
        pid = self._pid(b.get("project"))
        return self._char(lambda: charcard.leave(preview.ensure_site(pid), str(b.get("id") or "")))

    def cast_one(self, q: dict) -> tuple[int, dict]:
        from . import charcard
        return self._char(lambda: charcard.one(self._cast_mcp(), str((q.get("id") or [""])[0])))

    def cast_import(self, b: dict) -> tuple[int, dict]:
        """⬆ This project's 📌 references → the global cast (copies; originals stay)."""
        from . import cast
        pid = self._pid(b.get("project"))
        return self._cast_do(lambda: cast.import_refs(self._cast_mcp(), preview.ensure_site(pid), pid))

    # ---------- 🎞 M4 video breakdown (Hermes does the work) ----------
    def bd_list(self, q: dict) -> tuple[int, dict]:
        return self._cast_do(lambda: {"ok": True, **self._cast_mcp().call("breakdown_list", {})})

    def bd_get(self, q: dict) -> tuple[int, dict]:
        bid = str((q.get("id") or [""])[0])
        return self._cast_do(lambda: {"ok": True, **self._cast_mcp().call("breakdown_get", {"id": bid})})

    def bd_search(self, q: dict) -> tuple[int, dict]:
        qq = str((q.get("q") or [""])[0])
        return self._cast_do(lambda: {"ok": True, **self._cast_mcp().call("breakdown_search", {"query": qq, "n": 12})})

    def bd_status(self, q: dict) -> tuple[int, dict]:
        key = str((q.get("key") or [""])[0])
        return self._cast_do(lambda: {"ok": True, **self._cast_mcp().call("job_get", {"key": key})})

    def bd_start(self, b: dict) -> tuple[int, dict]:
        """🎞 Break a project video down. Only files inside the project folder; Hermes guards its own folders too."""
        from . import shelf
        root = preview.ensure_site(self._pid(b.get("project"))).resolve()
        p = shelf._safe(root, str(b.get("path") or ""))
        if not p or not p.is_file():
            return 200, {"ok": False, "icon": "🎞", "message": "Pick a video in this project first."}
        return self._cast_do(lambda: {"ok": True, **self._cast_mcp().call(
            "video_breakdown", {"path": str(p), "title": p.stem, "private": bool(b.get("private"))})})

    def bd_make(self, b: dict) -> tuple[int, dict]:
        from . import rip
        root = preview.ensure_site(self._pid(b.get("project")))
        return self._cast_do(lambda: rip.make_like(self._cast_mcp(), root, str(b.get("id") or ""), int(b.get("scene") or 0)))

    def bd_frame(self, b: dict) -> tuple[int, dict]:
        from . import rip
        root = preview.ensure_site(self._pid(b.get("project")))
        return self._cast_do(lambda: rip.use_frame(self._cast_mcp(), root, str(b.get("id") or ""), int(b.get("scene") or 0)))

    # ---------- 🎨 R2 official styles ----------
    def _style_ctx(self, b: dict):
        proj = store.project(self._pid(b.get("project")))
        return proj, preview.ensure_site(proj["id"])

    def styles_get(self, q: dict) -> tuple[int, dict]:
        from . import styles
        proj, root = self._style_ctx(q)
        ch = styles.chosen(root)
        return 200, {"ok": True, "styles": styles.all_styles(), "chosen": ch["name"] if ch else "",
                     "proposal": styles.proposal(root, proj["id"])}

    def styles_make(self, b: dict) -> tuple[int, dict]:
        """🔒 Make this an official style — from kept result #n of this project."""
        from . import shelf, styles
        proj, root = self._style_ctx(b)
        item = next((x for x in shelf.view(root)["kept"] if str(x.get("n")) == str(b.get("n"))), None)
        if item is None:
            return 200, {"ok": False, "icon": "🗄", "message": "Keep it first (✅ Keep) — only kept results can become a style."}
        return 200, styles.promote(root, str(b.get("name") or ""), item, proj.get("name") or proj["id"])

    def styles_choose(self, b: dict) -> tuple[int, dict]:
        from . import styles
        _, root = self._style_ctx(b)
        return 200, styles.choose(root, str(b.get("name") or ""))

    def styles_answer(self, b: dict) -> tuple[int, dict]:
        from . import styles
        proj, root = self._style_ctx(b)
        return 200, styles.answer(root, proj["id"], str(b.get("sig") or ""), str(b.get("answer") or ""),
                                  str(b.get("name") or ""), proj.get("name") or proj["id"])

    # ---------- 🏃 Motion Presets (2026-11-25) ----------
    def motions_get(self, q: dict) -> tuple[int, dict]:
        from . import motions as MO
        one = lambda k: str((q.get(k) or [""])[0]) if isinstance(q.get(k), list) else str(q.get(k) or "")   # noqa: E731
        return 200, MO.public(one("q"), one("shelf"))

    def motion_scene_view(self, root, scene=None, notes=None) -> dict:
        from . import motion_make as MM, motions as MO, timeline as TL
        scene = TL.load(root) if scene is None else scene
        P = MM.presets_for(scene)
        cast = []
        try:
            from . import rip
            cast = rip.cast_names(self._cast_mcp(), root)
        except Exception:                                        # noqa: BLE001 — offline: people are typed by hand
            pass
        pic, vid = MM.plan(scene, "picture", "local", self.cfg), MM.plan(scene, "video", "local", self.cfg)
        return {"ok": True, "scene": scene, "resolved": TL.resolve(scene), "rows": TL.rows(scene), "words": TL.to_words(scene, P),
                "length": TL.length(scene), "warn": TL.too_busy(scene, self.cfg), "max_actions": TL.max_actions(self.cfg),
                "presets": {k: MO.card(p) for k, p in P.items()}, "cast": cast, "notes": notes or [],
                "plan": {"pictures": pic["n"], "clips": vid["n"], "clip_max_s": vid.get("max_s"), "seconds": vid.get("seconds", 0)}}

    def motion_scene_get(self, q: dict) -> tuple[int, dict]:
        _, root = self._style_ctx(q)
        return 200, self.motion_scene_view(root)

    def motion_scene_set(self, b: dict) -> tuple[int, dict]:
        """Words box or blocks — whichever he changed; the other is rebuilt. {add: {preset, who}} taps a preset in."""
        from . import motions as MO, timeline as TL
        _, root = self._style_ctx(b)
        old = TL.load(root)
        notes = []
        if isinstance(b.get("words"), str):
            P = {p["id"]: p for p in MO.all_motions()}
            people = [str(x) for x in (b.get("people") or old["people"])]
            scene, notes = TL.from_words(b["words"], P, people, old)
        elif isinstance(b.get("scene"), dict):
            scene = b["scene"]
        else:
            scene = old
        if isinstance(b.get("add"), dict) and MO.get(str(b["add"].get("preset") or "")):
            p = MO.get(str(b["add"]["preset"]))
            scene = TL.clean(scene)
            prev = scene["blocks"][-1]["id"] if scene["blocks"] and b["add"].get("then", True) else None
            scene["blocks"].append({"preset": p["id"], "who": b["add"].get("who") or {}, "after": prev, "dur": p["seconds"],
                                    "feel": p["feel"], "moment": ""})
        if b.get("split"):
            scene = TL.split_busy(scene, self.cfg)
        if isinstance(b.get("people"), list):
            scene = {**TL.clean(scene), "people": [str(x)[:30] for x in b["people"]][:MO.MAX_PEOPLE]}
        return 200, self.motion_scene_view(root, TL.save(root, scene), notes)

    def motion_save(self, b: dict) -> tuple[int, dict]:
        from . import motion_fill
        return 200, motion_fill.save(str(b.get("run") or ""), b)

    def motion_delete(self, b: dict) -> tuple[int, dict]:
        from . import motions as MO
        return 200, MO.delete(str(b.get("id") or ""))

    def shelf_done(self, b: dict) -> tuple[int, dict]:
        from . import shelf
        return 200, {"ok": True, "done_at": shelf.set_done(preview.ensure_site(self._pid(b.get("project"))), bool(b.get("done")))}

    def shelf_keep(self, b: dict) -> tuple[int, dict]:
        from . import shelf
        try:
            r = self._shelf_run(b)
            from . import styles
            item = shelf.keep(r.root, r.id, r.task, r.made_view(), self._seen(r), styles.facts(r))
            self._craft_verdict(r.id, True)
            return 200, {"ok": True, "item": item}
        except (ValueError, KeyError) as e:
            return 200, {"ok": False, "code": "shelf", "icon": "🗄",
                         "message": "Can't find that run — it may be from before a Lab restart." if isinstance(e, KeyError) else str(e)}

    def shelf_toss(self, b: dict) -> tuple[int, dict]:
        from . import shelf
        try:
            r = self._shelf_run(b)
            made, undone = r.made_view(), []
            new = {m["path"] for m in made if m.get("new")}
            for st in reversed(list(r.steps)):                  # edits to files that were already there go back first
                if st.get("diff") and not st.get("undone") and st.get("path") and st["path"] not in new:
                    try:
                        r.undo_step(int(st.get("n") or 0))
                        undone.append(st["path"])
                    except Exception:                           # noqa: BLE001 — one stuck undo must not block the rest
                        pass
            item = shelf.toss(r.root, r.id, r.task, made, sorted(set(undone)), self._seen(r))
            return 200, {"ok": True, "item": item, "run": r.view()}
        except (ValueError, KeyError) as e:
            return 200, {"ok": False, "code": "shelf", "icon": "🗄",
                         "message": "Can't find that run — it may be from before a Lab restart." if isinstance(e, KeyError) else str(e)}

    def shelf_restore(self, b: dict) -> tuple[int, dict]:
        from . import shelf
        try:
            return 200, {"ok": True, **shelf.restore(preview.ensure_site(self._pid(b.get("project"))), str(b.get("run") or ""))}
        except ValueError as e:
            return 200, {"ok": False, "code": "shelf", "icon": "🗄", "message": str(e)}

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
            self._craft_verdict(r.id, False)
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
        nb = B.norm(req, ctypes)
        if nb["kind"] == "story":                                  # 📖 M3: a still per shot (words-only = a few writer replies)
            kind, req["n"] = "story", nb["n"]
        if nb["kind"] in ("motion", "motionfill"):                 # 🏃 Motion Presets: priced by plan in the run (Venice card)
            kind = nb["kind"]
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

    # 🪄 Prompt improvement cycle (Scott 2026-11-24: "i want my prompts to get an improvement cycle"). Same route, mode "prompt":
    # the writer keeps every word he gave and adds only what the kind of work is missing. "previous" + "fix" = the next round.
    IMPROVE_SYS = ("Scott typed a prompt for the AI Lab. Make it a stronger prompt for {what}. Keep his subject and every word "
                   "and detail he gave: do not remove, soften or swap any of it, and add no warnings, notes or comments. "
                   "Add only what is missing: {adds}. Plain words, one paragraph, no lists, no quotes, at most {words} "
                   "words. Reply with the improved prompt only.")
    IMPROVE_KINDS = {"video": ("a short video", "framing, light, setting, what moves and how the camera moves", 110),
                     "image": ("a picture", "framing, light, setting, mood and fine detail", 110),
                     "text": ("a piece of writing", "voice, length, shape and who it is for", 120),
                     "build": ("software an AI builder will make", "what it does, what is on the screen and how to check it works", 160),
                     "": ("the AI Lab", "the details a model needs to do it well", 140)}

    @staticmethod
    def _taste(root) -> dict:
        """🧠 remodel M3: what he ✅ kept and 🗑 threw away in this project — the improver leans toward the first, away from the second."""
        from . import shelf
        try:
            v = shelf.view(root)
        except Exception:                                        # noqa: BLE001 — taste is a bonus, never a blocker
            return {"kept": [], "tossed": []}
        def line(x):                                             # 👁 M1: + what the vision model saw and how well it matched
            t, s = str(x.get("task") or "").split("\n")[0].strip()[:200], x.get("seen") or {}
            if not t or not (s.get("caption") or s.get("score") is not None):
                return t
            bits = ([f"{s['score']}% match"] if s.get("score") is not None else []) + ([f"it showed: {s['caption'][:160]}"] if s.get("caption") else [])
            return f"{t} [👁 {' — '.join(bits)}]"
        uniq = lambda xs: list(dict.fromkeys(a for a in xs if a))                # noqa: E731
        out = {"kept": uniq(line(x) for x in v["kept"][-5:]), "tossed": uniq(line(x) for x in v["tossed"][-5:])}
        try:                                                     # 🎨 R2: + the chosen official style's promoted lessons
            from . import styles
            st = styles.chosen(root)
            if st and st.get("prompt_lessons"):
                out["style"] = {"name": st["name"], "lessons": st["prompt_lessons"][-10:]}
        except Exception:                                        # noqa: BLE001
            pass
        try:                                                     # 🎞 M4: shot recipes he made from video scenes (recipe shelf)
            from . import rip
            rs = [x.get("words") for x in rip.shelf(root)[-5:] if x.get("words")]
            if rs:
                out["recipes"] = rs
        except Exception:                                        # noqa: BLE001
            pass
        return out

    @staticmethod
    def _seen(r) -> dict | None:
        from . import eyes
        return eyes.seen(list(getattr(r, "pictures", None) or []) + list(getattr(r, "videos", None) or []))

    def _improve_msgs(self, b: dict, text: str, taste: dict | None = None) -> list[dict]:
        ids = [x for x in (b.get("ctypes") or []) if isinstance(x, str)]
        kind = next((k for k in ("video", "image", "text") if k in ids), "build" if ids else "")
        what, adds, words = self.IMPROVE_KINDS[kind]
        prev, fix = str(b.get("previous") or "").strip()[:4000], str(b.get("fix") or "").strip()[:600]
        user = "His words: " + text
        if taste and taste.get("kept"):
            user += "\n\nPrompts he kept in this project (the kind of detail that worked for him): " + " || ".join(taste["kept"])
        if taste and taste.get("tossed"):
            user += "\n\nPrompts he threw away (do not steer toward these): " + " || ".join(taste["tossed"])
        if taste and taste.get("style"):
            user += f"\n\nLessons from his official style “{taste['style']['name']}”: " + " || ".join(taste["style"]["lessons"])
        if taste and taste.get("recipes"):
            user += "\n\nShot recipes he took from videos in this project (framing, camera and light that he liked): " + " || ".join(taste["recipes"])
        if prev:
            user += "\n\nYour last version: " + prev + ("\n\nHe says to fix: " + fix if fix else "\n\nGive a fresh, different take.")
        return [{"role": "system", "content": self.IMPROVE_SYS.format(what=what, adds=adds, words=words)}, {"role": "user", "content": user}]

    def agent_rephrase(self, b: dict) -> tuple[int, dict]:
        """🪄 Help me say it: rough words → a clear change request Scott can edit before it runs."""
        if not self.cfg["flags"]["agent"]:
            return _off("agent")
    def _craft_verdict(self, run_id: str, keep: bool) -> None:
        """📓 ✅ Keep / 🗑 Throw away counts on the craft notes that run used."""
        if self.cfg["flags"].get("craft"):
            from . import craft
            craft.verdict(run_id, keep)

        improve = b.get("mode") == "prompt"
        text = str(b.get("text") or "").strip()[:4000 if improve else 1500]
        if not text:
            return 400, {"ok": False, "code": "bad_args", "icon": "✏️", "message": "Type what you want changed first."}
        proj = store.project(self._pid(b.get("project")))
        made = ", ".join(str(x)[:80] for x in (b.get("made") or [])[:8] if isinstance(x, str))
        ctx = f"What was made: {made}.\n" if made else ""
        from . import picture
        msgs = [{"role": "system", "content": self.REPHRASE_SYS}, {"role": "user", "content": ctx + "His words: " + text}]
        max_tok, max_len, cap, job = 300, 1200, 0.05, "lab-rephrase"
        if improve:
            taste = self._taste(preview.ensure_site(proj["id"]))
            msgs, max_tok, max_len, cap, job = self._improve_msgs(b, text, taste), 900, 4000, 0.10, "lab-improve"
        usd, why = 0.0, ""
        for prov, model in self._rephrase_writers(b):            # 2026-11-24 live: "⏳ is not a valid model ID" (HTTP 400)
            try:
                r = self.lab.chat(proj, prov, model, msgs, max_tok, cap_usd=cap, task=job)
            except Exception as e:                               # noqa: BLE001 — try the next writer
                why = f"{model}: {str(e)[:120]}"
                continue
            usd += float(r.usd or 0)
            out = (r.text or "").strip().strip('"').strip()
            if out and len(out) <= max_len and not picture.REFUSAL_RX.search(out[:80]):
                return 200, {"ok": True, "text": out, "usd": round(usd, 6), "writer": f"{prov}/{model}",
                             **({"learned": {"kept": len(taste["kept"]), "tossed": len(taste["tossed"])}} if improve else {})}
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
        if b.get("picture") or b.get("mode") == "prompt":     # 🪄 improve: 🔓 uncensored writers first (Scott's default)
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
                               str(b.get("folder") or ""), plats, str(b.get("orientation") or "any"),
                               str(b.get("home_group") or ""))

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

    def review_shots(self, b: dict) -> tuple[int, dict]:
        """📸 Before | After pictures for a waiting change (2026-11-25)."""
        return 200, {"ok": True, **review.make_shots(str(b.get("id") or ""))}

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

        def _refused(self) -> bool:
            """2026-11-24 online Lab: only Scott (gandalf itself, or his Tailscale login). True = answered 403."""
            if gate.allowed(self.headers, self.client_address[0], app.cfg):
                return False
            if urlparse(self.path).path.startswith("/api/"):
                self._send(403, {"ok": False, "code": "not_scott", "icon": "🔒",
                                 "message": "Only Scott can use the AI Lab — sign in to Tailscale as yourself."})
            else:
                self._send(403, gate.REFUSED_HTML, "text/html; charset=utf-8")
            return True

        def do_GET(self):                                                # noqa: N802
            if self._refused():
                return
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
            if u.path == "/api/shelf/source":
                return self._run(app.shelf_source, q)
            if u.path == "/api/shelf":
                return self._run(app.shelf_get, q)
            if u.path == "/loop":                          # 🔁 Creative Loop page (2026-11-25)
                return self._send(200, (WEB / "loop.html").read_bytes(), "text/html; charset=utf-8")
            if u.path == "/api/loop/pic":                  # 🔁 a loop picture — only from Hermes pictures/ai-lab/
                from . import loop as loopmod              # noqa: PLC0415
                b_, ct_ = loopmod.picture(str((q.get("path") or [""])[0]))
                return self._send(200, b_, ct_) if b_ else self._send(404, b"Not a loop picture.", "text/plain; charset=utf-8")
            if u.path in ("/api/loop/job", "/api/loop/jobs", "/api/loop/estimate", "/api/loop/trust"):
                return self._run(app.loop_call, u.path.rsplit("/", 1)[1], q)
            if u.path == "/api/refs":                      # 🎭 M2 the project's reference pictures (cast strip)
                return self._run(app.refs_get, q)
            if u.path == "/api/breakdown/pic":             # 🎞 M4 a scene frame — only from Hermes's breakdowns folder
                from . import rip as ripmod
                fp = ripmod.frame_file(str((q.get("path") or [""])[0]))
                return self._send(200, fp.read_bytes(), "image/jpeg") if fp else self._send(404, b"Not a breakdown frame.", "text/plain; charset=utf-8")
            if u.path in ("/api/breakdowns", "/api/breakdown", "/api/breakdown/search", "/api/breakdown/status"):
                return self._run(getattr(app, {"/api/breakdowns": "bd_list", "/api/breakdown": "bd_get",
                                               "/api/breakdown/search": "bd_search", "/api/breakdown/status": "bd_status"}[u.path]), q)
            if u.path == "/api/cast/pic":                  # 🎭 R1 a cast thumbnail — only inside Hermes's assets folder
                from . import cast as castmod
                b_, ct_ = castmod.picture(str((q.get("path") or [""])[0]))
                return self._send(200, b_, ct_) if b_ else self._send(404, b"Not a cast picture.", "text/plain; charset=utf-8")
            if u.path == "/api/cast/one":                  # 📇 asset library M1: one character card in full
                return self._run(app.cast_one, q)
            if u.path == "/api/cast":                      # 🎭 R1 global cast + this project's chosen cast
                return self._run(app.cast_get, q)
            if u.path == "/api/story":                     # 📖 M3 story bible + chapters of this project
                return self._run(app.story_get, q)
            if u.path == "/api/motions":                   # 🏃 Motion Presets library (search, shelves)
                return self._run(app.motions_get, q)
            if u.path == "/craft":                         # 📓 Craft Book page (2026-11-25)
                return self._send(200, (WEB / "craft.html").read_bytes(), "text/html; charset=utf-8")
            if u.path == "/api/craft":
                return self._run(app.craft_get, q)
            if u.path == "/api/motion/scene":              # 🏃 this project's timeline (rows, words, plan)
                return self._run(app.motion_scene_get, q)
            if u.path == "/api/motion/file":               # 🏃 a preset's preview / frame / pose — only inside its folder
                from . import motions as MOmod
                fp = MOmod.asset(str((q.get("id") or [""])[0]), str((q.get("f") or [""])[0]))
                ct = {".svg": "image/svg+xml", ".mp4": "video/mp4", ".png": "image/png", ".webp": "image/webp"}.get(fp.suffix.lower(), "image/jpeg") if fp else ""
                return self._send(200, fp.read_bytes(), ct) if fp else self._send(404, b"Not a motion file.", "text/plain; charset=utf-8")
            if u.path == "/api/styles":                    # 🎨 R2 official styles + the project's choice + a proposal
                return self._run(app.styles_get, q)
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
            if u.path == "/api/review/shot":                     # 📸 one Before | After picture (png)
                from . import shots as _shots                    # noqa: PLC0415
                png = _shots.picture(config.home() / "approvals", (q.get("id") or [""])[0], (q.get("side") or [""])[0])
                return self._send(200, png, "image/png") if png else self._send(404, b"No such picture.", "text/plain; charset=utf-8")
            if u.path == "/api/agent/shot":
                png = app.agent_shot((q.get("id") or [""])[0], (q.get("name") or [""])[0])
                return self._send(200, png, "image/png") if png else self._send(404, b"No such picture.", "text/plain; charset=utf-8")
            if u.path == "/api/recover":
                return self._run(lambda: (200, {"ok": True, "fields": store.recover((q.get("project") or [""])[0])}))
            return self._send(404, {"ok": False, "code": "not_found"})

        def do_POST(self):                                               # noqa: N802
            if self._refused():
                return
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
            if p == "/api/agent/start":
                return self._run(app.agent_start, b)
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
            if p in ("/api/shelf/keep", "/api/shelf/toss", "/api/shelf/restore", "/api/shelf/done"):
                return self._run({"keep": app.shelf_keep, "toss": app.shelf_toss, "restore": app.shelf_restore,
                                  "done": app.shelf_done}[p.rsplit("/", 1)[1]], b)
            if p == "/api/where/open":
                return self._run(app.where_open, b)
            if p in ("/api/loop/plan", "/api/loop/run", "/api/loop/rate", "/api/loop/spend_ok", "/api/loop/author"):
                return self._run(app.loop_call, p.rsplit("/", 1)[1], b)
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
            if p == "/api/review/shots":                   # 📸 Before | After pictures (2026-11-25)
                return self._run(app.review_shots, b)
            if p in ("/api/refs/pin", "/api/refs/unpin"):
                return self._run(getattr(app, "refs_" + p.rsplit("/", 1)[1]), b)
            if p in ("/api/breakdown/start", "/api/breakdown/make", "/api/breakdown/frame"):
                return self._run(getattr(app, "bd_" + p.rsplit("/", 1)[1]), b)
            if p == "/api/story/bible":                    # 📖 M3 edit the story bible
                return self._run(app.story_bible, b)
            if p in ("/api/cast/character", "/api/cast/use", "/api/cast/leave"):   # ⭐ 📇 asset library M1
                return self._run(getattr(app, "cast_" + p.rsplit("/", 1)[1]), b)
            if p in ("/api/cast/choose", "/api/cast/import"):
                return self._run(getattr(app, "cast_" + p.rsplit("/", 1)[1]), b)
            if p in ("/api/motion/scene", "/api/motion/save", "/api/motion/delete"):   # 🏃 Motion Presets
                return self._run(getattr(app, {"/api/motion/scene": "motion_scene_set", "/api/motion/save": "motion_save",
                                               "/api/motion/delete": "motion_delete"}[p]), b)
            if p in ("/api/styles/make", "/api/styles/choose", "/api/styles/answer"):
                return self._run(getattr(app, "styles_" + p.rsplit("/", 1)[1]), b)
            if p.startswith("/api/craft/"):
                return self._run(app.craft_post, p[len("/api/craft/"):], b)
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

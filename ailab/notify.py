"""📱 Phone pings (2026-11-24, M5): Scott gets ONLY "finished" or "stuck" (his rule, 2026-11-23).

Uses the same Hermes ntfy server the Night Shift brief uses (~/hermes-forge/alerts.json url/token) — Iris/the phone
already receive that. Stuck = no new step for stuck_after_s, OR the run ended without proof (failed, capped,
unproven). One ping per run. Silent when alerts.json has no ntfy channel. Never sends file contents or keys.
"""
from __future__ import annotations

import json
import threading
import time
import urllib.request
from pathlib import Path

ALERTS = Path.home() / "hermes-forge" / "alerts.json"
DEFAULT_TOPIC = "hermes-night"           # UNVERIFIED that Iris subscribes to it on the phone — the night brief uses it
NOT_PROVEN = {"failed", "capped", "unproven", "refused"}


def send(title: str, body: str, topic: str = DEFAULT_TOPIC, alerts: Path | None = None, opener=None) -> bool:
    try:
        c = json.loads((alerts or ALERTS).read_text())
        if c.get("channel") != "ntfy" or not c.get("url"):
            return False
        payload = {"topic": topic, "title": title[:120], "message": body[:500], "priority": 3, "tags": ["test_tube"]}
        req = urllib.request.Request(str(c["url"]).rstrip("/"), data=json.dumps(payload).encode(), method="POST")
        req.add_header("Content-Type", "application/json")
        if c.get("token"):
            req.add_header("Authorization", f"Bearer {c['token']}")
        with (opener or urllib.request.urlopen)(req, timeout=8) as r:   # noqa: S310 — operator-set loopback URL
            return 200 <= r.status < 300
    except Exception:                                                  # noqa: BLE001 — a ping is never worth a crash
        return False


def verdict(run) -> str:
    """'finished' · 'stuck' · '' (nothing to say yet / stopped by Scott himself)."""
    if getattr(run, "is_lane", False):
        return ""
    if run.state == "done":
        return "finished"
    if run.state in NOT_PROVEN:
        return "stuck"
    if run.state == "running" and run.stuck_info()["stuck"]:
        return "stuck"
    return ""


def message(run, kind: str) -> tuple[str, str]:
    task = (run.task.split("\n")[0])[:80]
    if kind == "finished":
        return f"✅ Lab finished — {run.project.get('name', run.project['id'])}", f"{task}\n{run.why[:200]}"
    return (f"🟠 Lab stuck — {run.project.get('name', run.project['id'])}",
            f"{task}\n{run.why[:200] or 'No progress for ' + str(round(run.stuck_info()['quiet_s'] / 60)) + ' min'}")


class Watcher:
    """Checks the runs every `every` seconds and pings once per run."""

    def __init__(self, agents, cfg: dict, every: float = 30.0, sender=send):
        self.agents, self.cfg, self.every, self.sender = agents, cfg, every, sender
        self.sent: dict[str, str] = {}
        # 2026-11-24: runs brought back after a Lab restart already pinged (or ended) before it — don't ping again
        for rid, run in list(agents.runs.items()):
            if getattr(run, "restored", False) and run.state not in ("running", "interrupted"):
                self.sent[rid] = verdict(run) or "ended"
        self._stop = threading.Event()

    def tick(self) -> list[tuple[str, str]]:
        out = []
        if not self.cfg.get("phone_pings", True):
            return out
        for rid, run in list(self.agents.runs.items()):
            k = verdict(run)
            if k and rid not in self.sent:
                title, body = message(run, k)
                self.sent[rid] = k
                self.sender(title, body, self.cfg.get("lab_ntfy_topic") or DEFAULT_TOPIC)
                out.append((rid, k))
        return out

    def start(self) -> None:
        def loop():
            while not self._stop.wait(self.every):
                try:
                    self.tick()
                except Exception:                                      # noqa: BLE001
                    pass
        threading.Thread(target=loop, daemon=True, name="lab-pings").start()

    def stop(self) -> None:
        self._stop.set()

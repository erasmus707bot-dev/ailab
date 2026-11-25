"""Caps. Standalone: a local ledger. Connected: Hermes CostLedger via spend_check/spend_record."""
from __future__ import annotations

import fcntl
import json
import os
import threading
import time
import uuid
from contextlib import contextmanager
from pathlib import Path


class SpendBlocked(Exception):
    pass


def _today() -> str:
    return time.strftime("%Y-%m-%d")


class LocalLedger:
    def __init__(self, path: Path, daily_cap_usd: float):
        self.path, self.cap = Path(path), float(daily_cap_usd)
        # 2026-11-24 parallel runs: money a call is about to spend is held until it's recorded, so two runs can't
        # both pass the cap check before either records (check + hold are one step under _held_lock).
        self._held: dict[str, float] = {}
        self._held_lock = threading.Lock()

    @contextmanager
    def _lock(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(f"{self.path}.lock", "w") as fh:
            fcntl.flock(fh, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(fh, fcntl.LOCK_UN)

    def _load(self) -> list[dict]:
        try:
            return json.loads(self.path.read_text() or "[]")
        except FileNotFoundError:
            return []

    def spent_today(self) -> float:
        return round(sum(e["usd"] for e in self._load() if e.get("day") == _today()), 6)

    def check(self, usd: float) -> tuple[bool, str]:
        s = self.spent_today() + sum(self._held.values())
        if s + usd > self.cap:
            return False, f"Lab daily cap reached: ${s:.2f}+${usd:.2f} > ${self.cap:.2f}"
        return True, ""

    def hold(self, usd: float) -> tuple[bool, str, str | None]:
        """Check the cap AND hold `usd` in one step. Release the token after record() (or on failure)."""
        with self._held_lock:
            ok, why = self.check(usd)
            if not ok:
                return False, why, None
            tok = uuid.uuid4().hex
            self._held[tok] = float(usd)
            return True, "", tok

    def release(self, tok: str | None) -> None:
        with self._held_lock:
            self._held.pop(tok or "", None)

    def record(self, provider: str, model: str, usd: float, tokens_in: int = 0, tokens_out: int = 0,
               task: str = "") -> None:
        with self._lock():
            rows = self._load()
            rows.append({"at": time.time(), "day": _today(), "provider": provider, "model": model,
                         "usd": round(usd, 6), "tokens_in": tokens_in, "tokens_out": tokens_out, "task": task[:80]})
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(rows))
            os.replace(tmp, self.path)


class HermesSpend:
    def __init__(self, mcp, category: str = "ailab"):
        self.mcp, self.category = mcp, category

    def spent_today(self) -> float:
        cats = self.mcp.call("spend_status").get("categories", {})
        return float((cats.get(self.category) or {}).get("today_usd") or 0)

    def check(self, usd: float) -> tuple[bool, str]:
        r = self.mcp.call("spend_check", {"usd": usd, "category": self.category})
        return bool(r.get("allowed")), r.get("why") or ""

    def record(self, provider, model, usd, tokens_in=0, tokens_out=0, task="") -> None:
        self.mcp.call("spend_record", {"usd": usd, "category": self.category, "provider": provider, "model": model,
                                       "tokens_in": tokens_in, "tokens_out": tokens_out, "task": task})

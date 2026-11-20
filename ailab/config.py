"""Lab settings. Lives OUTSIDE the repo (~/.config/ailab by default; AILAB_HOME overrides)."""
from __future__ import annotations

import json
import os
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

DEFAULTS: dict = {
    "mode": "standalone",                 # standalone | connected
    "daily_cap_usd": 2.0,                 # standalone ledger cap
    "compare_cap_usd": 0.50,              # one comparison run
    "category": "ailab",                  # Hermes CostLedger category (connected)
    "hermes_mcp_url": "http://127.0.0.1:8790/mcp",
    "hermes_token_file": str(Path.home() / "hermes-forge/mcp/tokens/ailab.token"),
    "models_ttl_s": 86400,
    # Used when a model has no price from /models or the table below. Deliberately high so caps hold.
    "fallback_price_per_mtok": {"in": 15.0, "out": 75.0},
    # USD per million tokens. Edit in config.json; prices drift — UNVERIFIED until checked.
    "prices_per_mtok": {},
    "base_urls": {},                      # override any provider's base URL
    # Feature flags. Switched on one at a time by Scott (M7). There is deliberately no API to flip them.
    "flags": {"router": False, "preview": False, "agent": False},
    "agent_step_cap": 12,                 # steps per agent run
    "agent_cap_usd": 0.50,                # $ per agent run (inside the daily cap)
    "port": 8850,                         # 8795 is Hermes SiteGen; 8850 unused in ~/hermes (2026-11-20)
    "hermes_url": "",                     # connected mode: where the ⌂ Hermes button goes
}


def home() -> Path:
    return Path(os.environ.get("AILAB_HOME") or Path.home() / ".config/ailab")


def cache_dir() -> Path:
    return Path(os.environ.get("AILAB_CACHE") or home() / "cache")


def inside_repo(p: Path) -> bool:
    try:
        Path(p).resolve().relative_to(REPO)
        return True
    except ValueError:
        return False


def load(overrides: dict | None = None) -> dict:
    cfg = json.loads(json.dumps(DEFAULTS))
    f = home() / "config.json"
    if f.exists():
        cfg.update(json.loads(f.read_text() or "{}"))
    cfg.update(overrides or {})
    cfg["flags"] = {**DEFAULTS["flags"], **{k: bool(v) for k, v in (cfg.get("flags") or {}).items()
                                           if k in DEFAULTS["flags"]}}
    if cfg["mode"] not in ("standalone", "connected"):
        raise ValueError("mode must be 'standalone' or 'connected'")
    return cfg

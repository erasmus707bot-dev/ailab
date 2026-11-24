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
    # Defaults checked 2026-11-23 (Claude: web search of Anthropic list prices; OpenRouter: roster notes, "about").
    # Without these the fallback ($15/$75) made a Sonnet step look 4x dearer and stopped a live run early.
    "prices_per_mtok": {
        "claude-sonnet-5-5": {"in": 2.0, "out": 10.0}, "claude-opus-5-5": {"in": 4.0, "out": 20.0},
        "thinkingmachines/inkling-2-small": {"in": 0.30, "out": 1.00},   # higher of two listed prices, 2026-11-23
        "openrouter/deepseek/deepseek-v4.1-flash": {"in": 0.30, "out": 1.20},
        "openrouter/minimax/minimax-m3.1-flash": {"in": 0.15, "out": 0.60},
        "openrouter/z-ai/glm-5.3": {"in": 1.40, "out": 4.40},
        "openrouter/moonshotai/kimi-k3.1-pro": {"in": 2.0, "out": 10.0},
        "openrouter/qwen/qwen3.8-max-0902": {"in": 2.0, "out": 6.0}},
    "base_urls": {},                      # override any provider's base URL
    # Feature flags. Switched on one at a time by Scott (M7). There is deliberately no API to flip them.
    "flags": {"router": False, "preview": False, "agent": False, "compare": False, "live": False},
    # 🪞 Show & change (2026-11-23): a running app's pages, Now beside New. Loopback apps only; "repo" must be a linked folder.
    "live_apps": {"hermes": {"url": "http://127.0.0.1:8780", "repo": "hermes", "web": "dist/hermes-local/hermes_local/web"}},
    "live_ports": [8860, 8861],          # Now, New — unused in ~/hermes (grep 2026-11-23); UNVERIFIED on the live box
    "agent_step_cap": 20,                 # steps per agent run (12 until 2026-11-22; game-code work needs read → edit → test rounds)
    "agent_max_tokens": 4096,             # per model reply (Hermes llm_call allows at most 4096)
    "extra_models": {},                   # {"openrouter": ["vendor/model-id"]} — added to that provider's model list
    "agent_cap_usd": 0.50,                # $ per agent run (inside the daily cap)
    "port": 8850,                         # 8795 is Hermes SiteGen; 8850 unused in ~/hermes (2026-11-20)
    "repos": {},                          # 🔗 linked code folders the agent may read + propose changes to: {"hermes": "~/hermes"}
    "programs": {},                       # 🔗 one program, several linked folders: {"hermes": ["hermes", "hermes-forge"]}
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
    cfg["prices_per_mtok"] = {**DEFAULTS["prices_per_mtok"], **(cfg.get("prices_per_mtok") or {})}   # config.json adds/overrides, never wipes
    cfg["flags"] = {**DEFAULTS["flags"], **{k: bool(v) for k, v in (cfg.get("flags") or {}).items()
                                           if k in DEFAULTS["flags"]}}
    if cfg["mode"] not in ("standalone", "connected"):
        raise ValueError("mode must be 'standalone' or 'connected'")
    return cfg

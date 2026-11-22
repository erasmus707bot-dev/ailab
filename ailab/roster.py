"""⭐ Recommended models (2026-11-22) — what to pick for which job, hosted and local.

Model ids and prices drift: each entry carries regex patterns that are matched against the provider's LIVE model list,
so a renamed dated id (…-1017) is still found. `id` is only the fallback when no live list is available (connected
mode, where Hermes makes the call). Sources read 2026-11-22: OpenRouter weekly rankings, Artificial Analysis runs
quoted by DeepInfra / gpuwerk / teamday guides, Ollama size tables. Prices are list prices then — UNVERIFIED now.
Hosted calls go through OpenRouter with zero-data-retention + no-training routing; a model whose only host does not
offer that will be refused by OpenRouter (the Lab shows the error) — see "zdr" below."""
from __future__ import annotations

import re

ROSTER: list[dict] = [
    # ---- hosted (OpenRouter) ----
    {"provider": "openrouter", "id": "deepseek/deepseek-v4.1-flash", "match": [r"^deepseek/deepseek-v4\.1-flash(-\d+)?$"],
     "job": "everyday coding agent — best score per dollar", "from": "DeepSeek · China · open weights (MIT)",
     "price": "about $0.30 in / $1.20 out per million", "zdr": "likely (open weights, many hosts)", "id_checked": False},
    {"provider": "openrouter", "id": "minimax/minimax-m3.1-flash", "match": [r"^minimax/minimax-m3\.1-flash"],
     "job": "cheapest agent runs; reads images", "from": "MiniMax · China · open weights",
     "price": "about $0.15 in / $0.60 out per million", "zdr": "likely (open weights)", "id_checked": True},
    {"provider": "openrouter", "id": "z-ai/glm-5.3", "match": [r"^z-ai/glm-5\.3$"],
     "job": "long multi-step coding and terminal work", "from": "Z.ai (Zhipu) · China · open weights",
     "price": "about $1.40 in / $4.40 out per million", "zdr": "likely (open weights)", "id_checked": True},
    {"provider": "openrouter", "id": "moonshotai/kimi-k3.1-pro", "match": [r"^moonshotai/kimi-k3\.1-pro"],
     "job": "the hardest long builds (strongest open model)", "from": "Moonshot · China · open weights",
     "price": "about $2 in / $10 out per million", "zdr": "likely (open weights)", "id_checked": True},
    {"provider": "openrouter", "id": "qwen/qwen3.8-max-0902", "match": [r"^qwen/qwen3\.8-max"],
     "job": "pictures + tools in one model", "from": "Alibaba Qwen · China · closed",
     "price": "about $2 in / $6 out per million", "zdr": "UNVERIFIED — Alibaba is the only host", "id_checked": True},
    # ---- local (Ollama on gandalf: RTX 2060 6 GB, 31 GB RAM) ----
    {"provider": "ollama", "id": "qwen3.5:4b", "match": [r"^qwen3\.5:4b"],
     "job": "fast local helper — fits fully on the 6 GB card", "from": "Alibaba Qwen · local", "price": "free", "pull": "qwen3.5:4b"},
    {"provider": "ollama", "id": "mimo-v2.6:9b", "match": [r"^mimo-v2\.6:9b"],
     "job": "best small local coder (6.6 GB — spills past the 6 GB card, slower)", "from": "Xiaomi MiMo · local · MIT",
     "price": "free", "pull": "mimo-v2.6:9b", "id_checked": False},
    {"provider": "ollama", "id": "qwen3.8:27b", "match": [r"^qwen3\.8:27b"],
     "job": "strongest local coder — about 18 GB, runs mostly on CPU: overnight jobs only", "from": "Alibaba Qwen · local · Apache 2.0",
     "price": "free", "pull": "qwen3.8:27b", "id_checked": False},
    {"provider": "ollama", "id": "qwen3.5:9b", "match": [r"^qwen3\.5:9b"],
     "job": "middle local model (already on gandalf; slow off the card)", "from": "Alibaba Qwen · local", "price": "free", "pull": "qwen3.5:9b"},
]


def for_provider(provider: str) -> list[dict]:
    return [e for e in ROSTER if e["provider"] == provider]


def arrange(provider: str, ids: list[str], live: bool, extra: list[str] | None = None) -> tuple[list[str], dict[str, str]]:
    """Model ids with the recommended ones first + {id: "what it's for"}.
    live=True: `ids` is the provider's real list — only models that are really there get a star.
    live=False (Hermes makes the call and lists just its defaults): the fallback ids are added, marked unconfirmed."""
    picks: dict[str, str] = {}
    front: list[str] = []
    for e in for_provider(provider):
        hit = sorted((m for m in ids if any(re.search(p, m) for p in e["match"])), reverse=True)     # newest dated id first
        if hit:
            front.append(hit[0])
            picks[hit[0]] = e["job"]
        elif not live and provider != "ollama":
            front.append(e["id"])
            picks[e["id"]] = e["job"] + " (id not confirmed)"
    extra = [m for m in (extra or []) if isinstance(m, str) and m and m not in front]
    rest = [m for m in ids if m not in front and m not in extra]
    return front + extra + rest, picks


def status(lab, project: dict | None = None) -> list[dict]:
    """Each roster entry: ready / pull it / needs a key — for the ⭐ list and `python3 -m ailab roster`."""
    cache: dict[str, tuple[list[str] | None, str, bool]] = {}
    out = []
    for e in ROSTER:
        prov = e["provider"]
        if prov not in cache:
            try:
                r = lab.list_models(prov, project or {})
                cache[prov] = ([m["id"] for m in r.get("models", [])], "", r.get("source") != "hermes")
                if r.get("source") == "hermes" and not r.get("has_key"):
                    cache[prov] = (cache[prov][0], "Hermes has no key for this provider yet", False)
            except Exception as ex:                                  # noqa: BLE001 — no key / Ollama off: report, don't crash
                cache[prov] = (None, str(ex)[:160], True)
        ids, err, live = cache[prov]
        hit = sorted((m for m in (ids or []) if any(re.search(p, m) for p in e["match"])), reverse=True)
        row = {k: e.get(k) for k in ("provider", "job", "from", "price", "zdr")}
        row["model"] = hit[0] if hit else e["id"]
        if hit:
            row["state"], row["todo"] = "ready", ""
        elif prov == "ollama":
            row["state"] = "not on this machine" if ids is not None else "Ollama not answering"
            row["todo"] = f"ollama pull {e['pull']}" if ids is not None else "start Ollama (ollama serve)"
        elif err:
            row["state"], row["todo"] = "needs a key", err
        elif not live:
            row["state"], row["todo"] = "ready (id not confirmed)", "Hermes makes the call; a wrong id comes back as a clear error"
        else:
            row["state"], row["todo"] = "not in the provider's list", "the id changed — pick the nearest name in the model list"
        out.append(row)
    return out

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
    {"provider": "openrouter", "id": "thinkingmachines/inkling-2-small", "match": [r"^thinkingmachines/inkling-2-small(-\d+)?$"],
     "job": "coding agent + reads screenshots, 1M context (pilot vs deepseek)", "from": "Thinking Machines · USA · open weights (Apache 2.0)",
     "price": "about $0.15–0.30 in / $0.50–1.00 out per million — UNVERIFIED (sources disagree)",
     "zdr": "likely (open weights, many hosts) — never the :free endpoint (logs prompts)", "id_checked": True},
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
    # ---- 🔓 uncensored (Scott 2026-11-24: "label the less censored models so I may make art in the most free ways") ----
    # Sources: morphllm "best uncensored llm" (2026-11-05), atlascloud / featherless 2026 guides. UNVERIFIED until a Compare probe.
    {"provider": "openrouter", "id": "nousresearch/hermes-4-405b", "match": [r"^nousresearch/hermes-4-405b"],
     "job": "🔓 uncensored — big general model, neutral alignment (stories, art prompts)", "from": "Nous Research · USA · open weights (Llama 3.1 base)",
     "price": "about $1 in / $3 out per million — UNVERIFIED", "zdr": "UNVERIFIED (open weights, several hosts)", "id_checked": False,
     "limits": "fewer"},
    {"provider": "openrouter", "id": "venice/uncensored", "match": [r"^venice/uncensored$"],
     "job": "🔓 uncensored — chat + creative writing; NO tool calling (not for builds)", "from": "Venice · USA · open-weight fine-tune",
     "price": "about $0.20 in / $0.90 out per million — UNVERIFIED",
     "zdr": "UNVERIFIED — never the :free endpoint (logs prompts)", "id_checked": False, "limits": "fewer"},
    # ---- 🔓 Venice direct (2026-11-24 art freedom). IDs + prices from docs.venice.ai/overview/models (2026-11-24). ----
    {"provider": "venice", "id": "venice-uncensored-1-2", "match": [r"^venice-uncensored-1-2$"],
     "job": "🔓 uncensored — picture prompt writer (keeps your words exactly); chat + creative writing",
     "from": "Venice · USA · open-weight fine-tune", "price": "$0.20 in / $0.90 out per million",
     "zdr": "Venice says private (no prompt storage) — UNVERIFIED by us", "id_checked": True, "limits": "fewer"},
    {"provider": "venice", "id": "deepseek-v4-1-flash-uncensored", "match": [r"^deepseek-v4-1-flash-uncensored$"],
     "job": "🔓 uncensored — stronger writer, longer stories", "from": "DeepSeek weights · hosted by Venice (USA)",
     "price": "$0.33 in / $1.32 out per million", "zdr": "Venice says private — UNVERIFIED by us", "id_checked": True,
     "limits": "fewer"},
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
    {"provider": "ollama", "id": "dolphin3:8b", "match": [r"^dolphin3:8b"],
     "job": "🔓 uncensored, local and private — stories, art prompts (fits the 6 GB card)", "from": "Dolphin (Eric Hartford) · local",
     "price": "free", "pull": "dolphin3:8b", "limits": "fewer"},
    {"provider": "ollama", "id": "hermes3:8b", "match": [r"^hermes3:8b"],
     "job": "🔓 uncensored, local — follows your system prompt closely (fits the 6 GB card)", "from": "Nous Research · local",
     "price": "free", "pull": "hermes3:8b", "limits": "fewer"},
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
    unc = lambda m: 0 if limits_tag(provider, m) == UNCENSORED else 1                  # noqa: E731 — policy: uncensored first
    return sorted(front, key=unc) + sorted(extra, key=unc) + sorted(rest, key=unc), picks


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
        row["limits"] = limits_tag(prov, e["id"])
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


# ---- "best use" + cost tier for EVERY model (2026-11-23) --------------------------------------------------------
# Starred models carry a curated job above. Everything else gets a tag read off its name — a guide, not a test
# result — and a $ tier from the price the provider lists (or the Lab's price table). Unknown price → no tier.
USE_RULES: list[tuple[str, str]] = [
    (r"embed|rerank|whisper|tts|moderation|guard|transcri", "⚙️ not a chat model"),
    (r"cod(e|er|ex|estral)|devstral|starcoder|swe-", "💻 coding"),
    (r"(^|[-/_:.])(vl|vision|omni|pixtral)([-/_:.]|$)|-vision|image-?(preview|understanding)", "🖼 sees images"),
    (r"(^|[-/_:.])(r1|qwq|o1|o3|o4)([-/_:.]|$)|reason|think|deep-?research|-dr\b", "🔬 reasoning / research"),
    (r"flash|mini|lite|haiku|nano|tiny|small|turbo|fast|instant|:[1-9](\.[0-9])?b\b", "⚡ fast & cheap"),
    (r"opus|ultra|max\b|large|405b|235b|480b|:[1-9][0-9]{1,2}b\b", "🧠 hardest work"),
]
# ---- 🔓 how strict a model is (2026-11-24) ----------------------------------------------------------------------
# 🔓 uncensored = a fine-tune made to refuse less (stories, art prompts, mature themes). 🔒 strict = the company that
# runs it filters on its side. No icon = normal. A guide from public write-ups, not a test — UNVERIFIED per model.
# Whatever the model: nothing sexual involving minors, no real person's likeness without consent.
LIMITS_FEWER_RX = re.compile(r"uncensored|abliterat|heretic|dolphin|(^|/)hermes-?[34]|nousresearch/hermes|venice/|lumimaid|"
                             r"euryale|mythomax|magnum|rocinante|cydonia|nemomix|unslop|lustify|^chroma$|aion-labs-aion", re.I)
# Policy (Scott 2026-11-24): every low- or no-censorship model carries the label "🔓 uncensored", and uncensored models
# come FIRST — in every model list, in every 💡 suggestion, and as the default writer / picture model.
UNCENSORED = "🔓 uncensored"
STRICT_PROVIDERS = {"claude", "qwen", "kimi", "gemini"}           # first-party APIs with provider-side filters
LIMITS_LEGEND = (" 🔓 uncensored = low or no censorship (made to refuse less — stories, art, mature themes); these "
                 "come first in every list · 🔒 = strict (the company filters on its side). A guide, not a test.")


def limits_tag(provider_name: str, model_id: str) -> str:
    """'🔓 uncensored' · '🔒' strict · '' normal."""
    for e in ROSTER:
        if e["provider"] == provider_name and e.get("limits") and any(re.search(p, model_id or "") for p in e["match"]):
            return UNCENSORED if e["limits"] == "fewer" else "🔒"
    if LIMITS_FEWER_RX.search(model_id or ""):
        return UNCENSORED
    if provider_name in STRICT_PROVIDERS or re.match(r"^(anthropic|openai|google)/", model_id or ""):
        return "🔒"
    return ""


USE_LEGEND = ("Tags come from the model's name (💻 coding · 🖼 sees images · 🔬 reasoning · ⚡ fast & cheap · 🧠 hardest work) "
              "— a guide, not a test. ⭐ rows were picked by hand. $ tiers: output price per million tokens — "
              "$ under 1 · $$ under 5 · $$$ under 15 · $$$$ above; free = local." + LIMITS_LEGEND)


def use_tag(model_id: str) -> str:
    m = (model_id or "").lower()
    for rx, tag in USE_RULES:
        if re.search(rx, m):
            return tag
    return "💬 general"


def cost_tier(out_per_token: float | None, local: bool = False) -> str:
    if local:
        return "free"
    if out_per_token is None:
        return ""
    per_m = out_per_token * 1e6
    if per_m <= 0:
        return "free"
    return "$" if per_m < 1 else "$$" if per_m < 5 else "$$$" if per_m < 15 else "$$$$"


def tags(provider_name: str, models: list[dict], price_of=None) -> dict[str, dict]:
    """{id: {"use": tag, "tier": "$$"}} for a provider's live list. price_of(model_id, listed) -> (in, out, priced) or None."""
    out = {}
    local = provider_name == "ollama"
    for m in models:
        mid = m.get("id") if isinstance(m, dict) else str(m)
        if not mid:
            continue
        tier = cost_tier(None, local)
        if not local:
            listed = m if isinstance(m, dict) else None
            if listed and listed.get("price_out") is not None:
                tier = cost_tier(float(listed["price_out"]))
            elif price_of:
                try:
                    pin, pout, priced = price_of(mid, listed)
                    tier = cost_tier(pout) if priced else ""
                except Exception:                                 # noqa: BLE001 — a price is a nicety
                    tier = ""
        out[mid] = {"use": use_tag(mid), "tier": tier, "limits": limits_tag(provider_name, mid)}
    return out

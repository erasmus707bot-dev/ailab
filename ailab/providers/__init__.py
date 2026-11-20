from __future__ import annotations

from .base import ChatResult, Provider
from .claude import Claude
from .openai_compat import HOSTS, OpenAICompat

NAMES = (*HOSTS, "claude")


def build(cfg: dict, transport) -> dict[str, Provider]:
    kw = {"prices_per_mtok": cfg.get("prices_per_mtok") or {}, "fallback": cfg.get("fallback_price_per_mtok")}
    urls = cfg.get("base_urls") or {}
    out: dict[str, Provider] = {n: OpenAICompat(n, transport, urls.get(n), **kw) for n in HOSTS}
    out["claude"] = Claude(transport, urls.get("claude"), **kw)
    return out


__all__ = ["NAMES", "ChatResult", "Claude", "OpenAICompat", "Provider", "build"]

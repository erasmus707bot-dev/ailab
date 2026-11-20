"""The one call path: privacy gate → cap check → key → provider → record spend."""
from __future__ import annotations

from . import config as _config
from . import privacy, providers
from .keys import LocalKeys
from .mcp_client import HermesMCP, HermesRefused
from .models import ModelCache
from .providers.base import ChatResult
from .spend import HermesSpend, LocalLedger, SpendBlocked
from .transport import http_json


class Lab:
    def __init__(self, cfg: dict | None = None, transport=None, keys=None, spend=None, mcp=None):
        self.cfg = cfg or _config.load()
        self.t = transport or http_json
        self.providers = providers.build(self.cfg, self.t)
        self.models = ModelCache(_config.cache_dir(), self.cfg["models_ttl_s"])
        self.connected = self.cfg["mode"] == "connected"
        if self.connected:
            # Hosted calls go through Hermes llm_call: Hermes holds the keys, checks the cap and records the cost.
            # Local Ollama still runs direct and needs no key.
            self.mcp = mcp or HermesMCP(self.cfg["hermes_mcp_url"], self.cfg["hermes_token_file"], self.t)
            self.keys = keys
            self.spend = spend or HermesSpend(self.mcp, self.cfg["category"])
        else:
            self.mcp = None
            self.keys = keys or LocalKeys()
            self.spend = spend or LocalLedger(_config.home() / "ledger.json", self.cfg["daily_cap_usd"])

    def provider(self, name: str):
        if name not in self.providers:
            raise KeyError(f"Unknown provider {name!r}. Choose from: {', '.join(self.providers)}")
        return self.providers[name]

    def list_models(self, name: str, project: dict | None = None, refresh: bool = False) -> dict:
        p = self.provider(name)
        privacy.check(project or {}, p)
        if self.connected and not p.local:
            for e in self.mcp.call("llm_providers").get("providers", []):
                if e["provider"] == name:
                    return {"provider": name, "source": "hermes", "has_key": e.get("has_key"),
                            "models": [{"id": m} for m in e.get("models", [])]}
            raise HermesRefused("not_enabled", f"Hermes has {name} turned off.",
                                "Turn it on in Hermes Settings → API keys.")
        return self.models.get(p, self.keys.get(p.key_name) if p.key_name else None, refresh)

    def _chat_via_hermes(self, project: dict, p, model, messages, max_tokens, task) -> ChatResult:
        try:
            r = self.mcp.call("llm_call", {"provider": p.name, "model": model, "messages": messages,
                                           "max_tokens": max_tokens, "category": self.cfg["category"],
                                           "task": task or project.get("name", ""),
                                           "sensitive": bool(project.get("sensitive"))})
        except HermesRefused as e:
            if e.code == "over_cap":
                raise SpendBlocked(e.message) from None
            if e.code in ("sensitive", "blocked_host"):
                raise privacy.PrivacyRefused(e.message) from None
            raise
        return ChatResult(r.get("text", ""), p.name, r.get("model", model), int(r.get("tokens_in") or 0),
                          int(r.get("tokens_out") or 0), float(r.get("usd") or 0), bool(r.get("priced", True)), r)

    def chat(self, project: dict, provider: str, model: str, messages: list[dict], max_tokens: int = 1024,
             cap_usd: float | None = None, task: str = "") -> ChatResult:
        p = self.provider(provider)
        privacy.check(project, p)                                  # before any key or byte leaves
        listed = self.models.lookup(p.name, model)
        est = p.estimate_usd(model, messages, max_tokens, listed)
        if cap_usd is not None and est > cap_usd:
            raise SpendBlocked(f"Estimated ${est:.4f} is over this run's cap of ${cap_usd:.2f}.")
        if self.connected and not p.local:
            return self._chat_via_hermes(project, p, model, messages, max_tokens, task)
        if not p.local:
            ok, why = self.spend.check(est)
            if not ok:
                raise SpendBlocked(why)
        key = self.keys.get(p.key_name) if p.key_name else None
        r = p.chat(model, messages, max_tokens, key, listed)
        if not p.local:
            self.spend.record(p.name, r.model, r.usd, r.tokens_in, r.tokens_out, task or project.get("name", ""))
        return r

    def status(self) -> dict:
        return {"mode": self.cfg["mode"], "spent_today_usd": self.spend.spent_today(),
                "providers": {n: {"host": p.host, "local": p.local} for n, p in self.providers.items()}}

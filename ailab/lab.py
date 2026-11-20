"""The one call path: privacy gate → cap check → key → provider → record spend."""
from __future__ import annotations

from . import config as _config
from . import privacy, providers
from .keys import HermesKeys, LocalKeys
from .mcp_client import HermesMCP
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
            self.mcp = mcp or HermesMCP(self.cfg["hermes_mcp_url"], self.cfg["hermes_token_file"], self.t)
            self.keys = keys or HermesKeys(self.mcp)
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
        return self.models.get(p, self.keys.get(p.key_name) if p.key_name else None, refresh)

    def chat(self, project: dict, provider: str, model: str, messages: list[dict], max_tokens: int = 1024,
             cap_usd: float | None = None, task: str = "") -> ChatResult:
        p = self.provider(provider)
        privacy.check(project, p)                                  # before any key or byte leaves
        listed = self.models.lookup(p.name, model)
        est = p.estimate_usd(model, messages, max_tokens, listed)
        if cap_usd is not None and est > cap_usd:
            raise SpendBlocked(f"Estimated ${est:.4f} is over this run's cap of ${cap_usd:.2f}.")
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

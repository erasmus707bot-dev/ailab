from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import urlparse


@dataclass
class ChatResult:
    text: str
    provider: str
    model: str
    tokens_in: int = 0
    tokens_out: int = 0
    usd: float = 0.0
    priced: bool = True            # False = cost came from the fallback price
    raw: dict = field(default_factory=dict, repr=False)


class Provider:
    name = ""
    base_url = ""
    key_name: str | None = None    # None = no key needed

    def __init__(self, transport, prices_per_mtok: dict | None = None, fallback: dict | None = None):
        self.t = transport
        self.prices = prices_per_mtok or {}
        self.fallback = fallback or {"in": 15.0, "out": 75.0}

    @property
    def host(self) -> str:
        return (urlparse(self.base_url).hostname or "").lower()

    @property
    def local(self) -> bool:
        return self.host in ("127.0.0.1", "localhost", "::1")

    # --- pricing -------------------------------------------------------------------------
    def price(self, model: str, listed: dict | None = None) -> tuple[float, float, bool]:
        """USD per token (in, out, priced?). Order: /models listing → config table → fallback."""
        if self.local:
            return 0.0, 0.0, True
        if listed and listed.get("price_in") is not None and listed.get("price_out") is not None:
            return float(listed["price_in"]), float(listed["price_out"]), True
        p = self.prices.get(f"{self.name}/{model}") or self.prices.get(model)
        if p:
            return p["in"] / 1e6, p["out"] / 1e6, True
        return self.fallback["in"] / 1e6, self.fallback["out"] / 1e6, False

    def estimate_usd(self, model: str, messages: list[dict], max_tokens: int, listed: dict | None = None) -> float:
        pin, pout, _ = self.price(model, listed)
        chars = sum(len(str(m.get("content", ""))) for m in messages)
        return round((chars / 3.5) * pin + max_tokens * pout, 6)     # /3.5 leans high on purpose

    # --- provider API --------------------------------------------------------------------
    def list_models(self, key: str | None) -> list[dict]:
        raise NotImplementedError

    def chat(self, model: str, messages: list[dict], max_tokens: int, key: str | None,
             listed: dict | None = None) -> ChatResult:
        raise NotImplementedError

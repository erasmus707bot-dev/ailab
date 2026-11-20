"""Direct Claude API (Messages). Prices come from config — /v1/models carries none."""
from __future__ import annotations

from .base import ChatResult, Provider


class Claude(Provider):
    name = "claude"
    key_name = "claude"

    def __init__(self, transport, base_url: str | None = None, **kw):
        super().__init__(transport, **kw)
        self.base_url = (base_url or "https://api.anthropic.com/v1").rstrip("/")

    def _headers(self, key: str | None) -> dict:
        return {"x-api-key": key or "", "anthropic-version": "2023-06-01"}

    def list_models(self, key):
        data = self.t("GET", f"{self.base_url}/models?limit=100", self._headers(key), None).get("data", [])
        return [{"id": m["id"], "name": m.get("display_name") or m["id"]} for m in data if m.get("id")]

    def chat(self, model, messages, max_tokens, key, listed=None) -> ChatResult:
        system = "\n\n".join(str(m["content"]) for m in messages if m.get("role") == "system")
        body = {"model": model, "max_tokens": max_tokens,
                "messages": [m for m in messages if m.get("role") != "system"]}
        if system:
            body["system"] = system
        r = self.t("POST", f"{self.base_url}/messages", self._headers(key), body)
        u = r.get("usage") or {}
        ti, to = int(u.get("input_tokens") or 0), int(u.get("output_tokens") or 0)
        pin, pout, priced = self.price(model, listed)
        text = "".join(b.get("text", "") for b in r.get("content") or [] if b.get("type") == "text")
        return ChatResult(text, self.name, r.get("model") or model, ti, to, round(ti * pin + to * pout, 6), priced, r)

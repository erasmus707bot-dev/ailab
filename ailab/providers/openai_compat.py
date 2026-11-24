"""One adapter for every OpenAI-compatible host: OpenRouter, Hugging Face router, Qwen, Kimi, Gemini, Ollama."""
from __future__ import annotations

from .base import ChatResult, Provider

# name → (base URL, key name). Base URLs other than OpenRouter/Ollama: UNVERIFIED against a live call.
HOSTS: dict[str, tuple[str, str | None]] = {
    "openrouter": ("https://openrouter.ai/api/v1", "openrouter"),
    "hf": ("https://router.huggingface.co/v1", "hf"),
    "qwen": ("https://dashscope-intl.aliyuncs.com/compatible-mode/v1", "qwen"),
    "kimi": ("https://api.moonshot.ai/v1", "kimi"),
    "gemini": ("https://generativelanguage.googleapis.com/v1beta/openai", "gemini"),   # 2026-11-24, Hermes-held key
    "ollama": ("http://127.0.0.1:11434/v1", None),
}


class OpenAICompat(Provider):
    def __init__(self, name: str, transport, base_url: str | None = None, **kw):
        super().__init__(transport, **kw)
        self.name = name
        url, self.key_name = HOSTS[name]
        self.base_url = (base_url or url).rstrip("/")

    def _headers(self, key: str | None) -> dict:
        return {"Authorization": f"Bearer {key}"} if key else {}

    def extra_body(self) -> dict:
        if self.name == "openrouter":
            # Zero data retention + no training providers + return real cost in usage.
            return {"provider": {"zdr": True, "data_collection": "deny"}, "usage": {"include": True}}
        if self.name == "ollama":
            # 2026-11-21 real run: qwen3.5 on gandalf's CPU spent minutes "thinking" before the first word and
            # timed out. Ollama's /v1 endpoint honours reasoning_effort "none" (it ignores think:false there).
            return {"reasoning_effort": "none"}
        return {}

    def list_models(self, key: str | None) -> list[dict]:
        out = []
        for m in self.t("GET", f"{self.base_url}/models", self._headers(key), None).get("data", []):
            pr = m.get("pricing") or {}
            item = {"id": m.get("id"), "name": m.get("name") or m.get("id")}
            try:
                item["price_in"], item["price_out"] = float(pr["prompt"]), float(pr["completion"])
            except (KeyError, TypeError, ValueError):
                pass
            out.append(item)
        return [m for m in out if m["id"]]

    def chat(self, model, messages, max_tokens, key, listed=None) -> ChatResult:
        body = {"model": model, "messages": messages, "max_tokens": max_tokens, **self.extra_body()}
        r = self.t("POST", f"{self.base_url}/chat/completions", self._headers(key), body)
        u = r.get("usage") or {}
        ti, to = int(u.get("prompt_tokens") or 0), int(u.get("completion_tokens") or 0)
        pin, pout, priced = self.price(model, listed)
        usd = float(u["cost"]) if u.get("cost") is not None else ti * pin + to * pout
        text = ((r.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
        return ChatResult(text, self.name, r.get("model") or model, ti, to, round(usd, 6),
                          priced or u.get("cost") is not None, r)

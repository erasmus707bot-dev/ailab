"""Privacy gate — runs before any key is fetched or any byte leaves the machine."""
from __future__ import annotations

from .providers.base import Provider

BLOCKED_HOST_SUFFIXES = ("deepseek.com",)       # DeepSeek first-party API (audit §3)


class PrivacyRefused(Exception):
    pass


def check(project: dict, provider: Provider) -> None:
    host = provider.host
    for s in BLOCKED_HOST_SUFFIXES:
        if host == s or host.endswith("." + s):
            raise PrivacyRefused(f"{host} is blocked (DeepSeek first-party API). Use the model via OpenRouter with ZDR.")
    if project.get("sensitive") and not provider.local:
        raise PrivacyRefused(f"Project {project.get('name', '?')!r} is marked sensitive: Ollama (local) only, "
                             f"not {provider.name}.")
    if provider.name == "openrouter" and not provider.extra_body().get("provider", {}).get("zdr"):
        raise PrivacyRefused("OpenRouter call without ZDR refused.")

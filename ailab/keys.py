"""Where provider keys come from. The Lab never reads Hermes Vault directly."""
from __future__ import annotations

import os
import stat
from pathlib import Path

from . import config

ENV_NAMES = {"openrouter": "OPENROUTER_API_KEY", "hf": "HF_TOKEN", "qwen": "DASHSCOPE_API_KEY",
             "kimi": "MOONSHOT_API_KEY", "claude": "ANTHROPIC_API_KEY"}


class KeyMissing(Exception):
    pass


def _env_file(path: Path) -> dict:
    if config.inside_repo(path):
        raise KeyMissing(f"Refusing a key file inside the repo ({path}). Keep it in {config.home()}.")
    if not path.exists():
        return {}
    if path.stat().st_mode & (stat.S_IRWXG | stat.S_IRWXO):
        raise KeyMissing(f"{path} is readable by others. Run: chmod 600 {path}")
    out = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip().strip('"').strip("'")
    return out


class LocalKeys:
    """Standalone: OS keyring (service 'ailab') → environment → ~/.config/ailab/keys.env (0600)."""

    def __init__(self, env_file: Path | None = None, use_keyring: bool = True):
        self.env_file = Path(env_file or config.home() / "keys.env")
        self.use_keyring = use_keyring

    def get(self, name: str) -> str:
        if self.use_keyring:
            try:
                import keyring                                    # noqa: PLC0415 — optional
                v = keyring.get_password("ailab", name)
                if v:
                    return v
            except Exception:                                     # noqa: BLE001 — no keyring backend is fine
                pass
        env = ENV_NAMES.get(name, name.upper())
        v = os.environ.get(env) or _env_file(self.env_file).get(env)
        if not v:
            raise KeyMissing(f"No {name} key. Set {env} in {self.env_file} (chmod 600) or the OS keyring.")
        return v


class HermesKeys:
    """Connected: Hermes hands over the key through its MCP server (tool 'provider_key')."""

    def __init__(self, mcp):
        self.mcp = mcp

    def get(self, name: str) -> str:
        from .mcp_client import HermesRefused                     # noqa: PLC0415
        try:
            v = self.mcp.call("provider_key", {"provider": name}).get("key")
        except HermesRefused as e:
            raise KeyMissing(f"Hermes did not give a {name} key: {e.message}") from None
        if not v:
            raise KeyMissing(f"Hermes has no {name} key.")
        return v

"""Standalone key lookup. In connected mode Hermes holds the keys and makes hosted calls (llm_call);
the Lab never sees Vault or a Hermes key."""
from __future__ import annotations

import os
import stat
from pathlib import Path

from . import config

ENV_NAMES = {"openrouter": "OPENROUTER_API_KEY", "hf": "HF_TOKEN", "qwen": "DASHSCOPE_API_KEY",
             "kimi": "MOONSHOT_API_KEY", "gemini": "GEMINI_API_KEY",
             "claude": "ANTHROPIC_API_KEY"}


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



# ---- 🔑 Keys page (2026-11-23): set / remove / status without ever echoing a key ----
KEY_RX_MIN, KEY_MAX = 8, 4096


def _keyring():
    try:
        import keyring                                            # noqa: PLC0415 — optional
        from keyring.backends.fail import Keyring as Fail         # noqa: PLC0415
        kr = keyring.get_keyring()
        return None if isinstance(kr, Fail) else keyring
    except Exception:                                             # noqa: BLE001
        return None


def _write_env_file(path: Path, kv: dict) -> None:
    if config.inside_repo(path):
        raise KeyMissing(f"Refusing to write a key file inside the repo ({path}).")
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write("# AI Lab keys — written by the 🔑 Keys page. Owner-only (0600). Never commit this file.\n")
        for k, v in sorted(kv.items()):
            f.write(f"{k}={v}\n")
    os.chmod(tmp, 0o600)
    tmp.replace(path)


class KeyStore(LocalKeys):
    """Where a key lives, and setting / removing one. Values never leave this module except to a provider call."""

    def status(self, name: str) -> dict:
        env = ENV_NAMES.get(name, name.upper())
        kr = _keyring() if self.use_keyring else None
        try:
            if kr and kr.get_password("ailab", name):
                return {"set": True, "source": "keyring"}
        except Exception:                                         # noqa: BLE001
            pass
        if os.environ.get(env):
            return {"set": True, "source": "environment"}
        try:
            if _env_file(self.env_file).get(env):
                return {"set": True, "source": "file"}
        except KeyMissing as e:
            return {"set": False, "source": "none", "problem": str(e)}
        return {"set": False, "source": "none"}

    def set(self, name: str, value: str) -> str:
        """Returns where it went: 'keyring' or 'file'. The OS keyring wins when it works; else keys.env (0600)."""
        value = (value or "").strip()
        if name not in ENV_NAMES:
            raise KeyMissing(f"No such provider: {name}.")
        if not (KEY_RX_MIN <= len(value) <= KEY_MAX) or any(c.isspace() for c in value):
            raise KeyMissing("That doesn't look like a key (too short, too long, or has spaces).")
        kr = _keyring() if self.use_keyring else None
        if kr:
            try:
                kr.set_password("ailab", name, value)
                return "keyring"
            except Exception:                                     # noqa: BLE001 — fall through to the file
                pass
        kv = _env_file(self.env_file)
        kv[ENV_NAMES[name]] = value
        _write_env_file(self.env_file, kv)
        return "file"

    def remove(self, name: str) -> list[str]:
        """Removes the key everywhere the Lab controls (keyring + file). The environment is not ours to change."""
        gone = []
        kr = _keyring() if self.use_keyring else None
        if kr:
            try:
                if kr.get_password("ailab", name):
                    kr.delete_password("ailab", name)
                    gone.append("keyring")
            except Exception:                                     # noqa: BLE001
                pass
        env = ENV_NAMES.get(name, name.upper())
        kv = _env_file(self.env_file)
        if env in kv:
            kv.pop(env)
            _write_env_file(self.env_file, kv)
            gone.append("file")
        return gone

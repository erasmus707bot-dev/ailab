"""Live /models lookup, cached per provider. A failed refresh falls back to the stale cache."""
from __future__ import annotations

import json
import time
from pathlib import Path


class ModelCache:
    def __init__(self, directory: Path, ttl_s: int = 86400, now=time.time):
        self.dir, self.ttl, self.now = Path(directory), ttl_s, now

    def _file(self, provider: str) -> Path:
        return self.dir / f"models_{provider}.json"

    def get(self, provider, key: str | None, refresh: bool = False) -> dict:
        f = self._file(provider.name)
        cached = json.loads(f.read_text()) if f.exists() else None
        if cached and not refresh and self.now() - cached["at"] < self.ttl:
            return {**cached, "source": "cache"}
        try:
            models = provider.list_models(key)
        except Exception as e:                                    # noqa: BLE001
            if cached:
                return {**cached, "source": "stale", "error": str(e)[:200]}
            raise
        data = {"at": self.now(), "provider": provider.name, "models": models}
        self.dir.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(data))
        return {**data, "source": "live"}

    def lookup(self, provider_name: str, model: str) -> dict | None:
        f = self._file(provider_name)
        if not f.exists():
            return None
        return next((m for m in json.loads(f.read_text())["models"] if m["id"] == model), None)

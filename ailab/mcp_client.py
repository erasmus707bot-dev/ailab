"""Client for the Hermes MCP server (HTTP, Bearer token). Connected mode only."""
from __future__ import annotations

import itertools
from pathlib import Path


class HermesRefused(Exception):
    def __init__(self, code: str, message: str, fix: str = ""):
        self.code, self.message, self.fix = code, message, fix
        super().__init__(f"Hermes refused ({code}): {message}" + (f" — {fix}" if fix else ""))


class HermesMCP:
    def __init__(self, url: str, token_file: str, transport):
        self.url, self.token_file, self.t = url, Path(token_file), transport
        self._ids = itertools.count(1)

    def __repr__(self) -> str:                      # never show the token
        return f"HermesMCP({self.url})"

    def _token(self) -> str:
        if not self.token_file.exists():
            raise HermesRefused("no_token", f"Token file {self.token_file} not found.",
                                "On gandalf: python3 -m forge.projects.mcp_server token add ailab")
        return self.token_file.read_text().strip()

    def call(self, tool: str, args: dict | None = None) -> dict:
        msg = {"jsonrpc": "2.0", "id": next(self._ids), "method": "tools/call",
               "params": {"name": tool, "arguments": args or {}}}
        r = self.t("POST", self.url, {"Authorization": f"Bearer {self._token()}"}, msg)
        if "error" in r:
            raise HermesRefused("rpc", str(r["error"].get("message")))
        res = r.get("result") or {}
        sc = res.get("structuredContent") or {}
        if res.get("isError") or sc.get("ok") is False:
            raise HermesRefused(sc.get("code", "error"), sc.get("message", "unknown"), sc.get("fix", ""))
        return sc

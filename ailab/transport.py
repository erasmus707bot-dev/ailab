"""Tiny stdlib HTTP JSON client. Errors never carry request headers (keys live there)."""
from __future__ import annotations

import json
import urllib.error
import urllib.request


class HttpError(Exception):
    def __init__(self, status: int, url: str, body: str):
        self.status, self.url, self.body = status, url, body[:300]
        super().__init__(f"HTTP {status} from {url}: {self.body}")


def http_json(method: str, url: str, headers: dict | None = None, body: dict | None = None,
              timeout: float = 60) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"Content-Type": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:      # noqa: S310 — fixed provider URLs
            raw = r.read()
    except urllib.error.HTTPError as e:
        raise HttpError(e.code, url, e.read().decode("utf-8", "replace")) from None
    except urllib.error.URLError as e:
        raise HttpError(0, url, str(e.reason)) from None
    return json.loads(raw or b"{}")

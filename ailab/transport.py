"""Tiny stdlib HTTP JSON client. Errors never carry request headers (keys live there)."""
from __future__ import annotations

import http.client
import json
import socket
import urllib.error
import urllib.parse
import urllib.request

# A local model (Ollama) may need minutes on its first call: it loads into memory and may think first.
LOCAL_TIMEOUT_S, HOSTED_TIMEOUT_S = 300, 120


class HttpError(Exception):
    def __init__(self, status: int, url: str, body: str):
        self.status, self.url, self.body = status, url, body[:300]
        super().__init__(f"HTTP {status} from {url}: {self.body}")


def http_json(method: str, url: str, headers: dict | None = None, body: dict | None = None,
              timeout: float | None = None) -> dict:
    if timeout is None:
        host = (urllib.parse.urlparse(url).hostname or "").lower()
        timeout = LOCAL_TIMEOUT_S if host in ("127.0.0.1", "localhost", "::1") else HOSTED_TIMEOUT_S
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"Content-Type": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:      # noqa: S310 — fixed provider URLs
            raw = r.read()
    except urllib.error.HTTPError as e:
        raise HttpError(e.code, url, e.read().decode("utf-8", "replace")) from None
    except urllib.error.URLError as e:
        if isinstance(e.reason, (TimeoutError, socket.timeout)):
            raise HttpError(0, url, f"no answer within {timeout:.0f} s") from None
        raise HttpError(0, url, str(e.reason)) from None
    except (TimeoutError, socket.timeout):
        raise HttpError(0, url, f"no answer within {timeout:.0f} s — a local model may still be loading; "
                                "try again") from None
    except (http.client.HTTPException, ConnectionError) as e:   # IncompleteRead / RemoteDisconnected / reset (2026-11-25 live)
        raise HttpError(0, url, f"the connection dropped mid-answer ({type(e).__name__}) — the service may have "
                                "restarted; try again") from None
    return json.loads(raw or b"{}")

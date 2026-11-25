"""Runs INSIDE the srt sandbox. Serves one project folder over stdin/stdout, one JSON line each way.

No imports from ailab (the sandbox can read only this folder and the project). No network, no sockets
(srt blocks them), no writes. Requests: {"op":"get","path":"a/b.css"} | {"op":"version"} | {"op":"ping"}.
"""
import base64
import hashlib
import json
import mimetypes
import os
import sys

ROOT = os.path.realpath(sys.argv[1])
MAX_FILE = 25_000_000   # 2026-11-24: Venice PNGs run 4–6 MB (a 5.6 MB picture showed 'Not found')
MAX_FILES = 2000
TYPES = {".js": "text/javascript", ".mjs": "text/javascript", ".css": "text/css", ".html": "text/html",
         ".svg": "image/svg+xml", ".json": "application/json", ".wasm": "application/wasm"}


def resolve(rel):
    rel = (rel or "").lstrip("/") or "index.html"
    if any(p.startswith(".") for p in rel.split("/") if p):
        return None
    p = os.path.realpath(os.path.join(ROOT, rel))
    if p != ROOT and not p.startswith(ROOT + os.sep):
        return None
    if os.path.isdir(p):
        p = os.path.join(p, "index.html")
    return p if os.path.isfile(p) else None


def version():
    h, n = hashlib.sha1(), 0
    for d, dirs, files in os.walk(ROOT):
        dirs[:] = sorted(x for x in dirs if not x.startswith("."))
        for f in sorted(files):
            if f.startswith("."):
                continue
            st = os.stat(os.path.join(d, f))
            h.update(f"{os.path.relpath(os.path.join(d, f), ROOT)}|{st.st_mtime_ns}|{st.st_size}\n".encode())
            n += 1
            if n >= MAX_FILES:
                return h.hexdigest()[:16]
    return h.hexdigest()[:16]


def handle(req):
    op = req.get("op")
    if op == "ping":
        return {"ok": True, "root": ROOT}
    if op == "version":
        return {"ok": True, "v": version()}
    if op == "get":
        p = resolve(req.get("path"))
        if not p:
            return {"ok": False, "status": 404}
        if os.path.getsize(p) > MAX_FILE:
            return {"ok": False, "status": 413}
        ext = os.path.splitext(p)[1].lower()
        ctype = TYPES.get(ext) or mimetypes.guess_type(p)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/json", "image/svg+xml", "text/javascript"):
            ctype += "; charset=utf-8"
        with open(p, "rb") as fh:
            return {"ok": True, "status": 200, "ctype": ctype, "b64": base64.b64encode(fh.read()).decode()}
    return {"ok": False, "status": 400}


def main():
    for line in sys.stdin:
        try:
            out = handle(json.loads(line))
        except Exception as e:  # noqa: BLE001 — one bad request must not kill the server
            out = {"ok": False, "status": 500, "error": type(e).__name__}
        sys.stdout.write(json.dumps(out) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()

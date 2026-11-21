"""Secret scan (M8) — run before the repo goes public, and on every 📋 Review package.

Looks at tracked + about-to-be-tracked files, AND the whole git history (a key removed later is still pushed).
A line can opt out with the marker `secretscan: test-fixture` (fake values in tests only). Fake values already in
git history are listed by sha256 (never the value) in `.secretscan-allow` at the repo root.
python3 -m ailab secretscan [path]  → exit 0 clean, 1 hits. Hits never print the value, only where it is.
"""
from __future__ import annotations

import hashlib
import re
import subprocess
from pathlib import Path

SECRET_RX = re.compile(
    r"(sk-[A-Za-z0-9_-]{20,}|sk-ant-[A-Za-z0-9_-]{10,}|ghp_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}"
    r"|AKIA[0-9A-Z]{16}|hf_[A-Za-z0-9]{30,}|xox[abprs]-[A-Za-z0-9-]{10,}|-----BEGIN [A-Z ]*PRIVATE KEY-----)")
ALLOW = "secretscan: test-fixture"
BAD_NAMES = re.compile(r"(^|/)(\.env[^/]*|keys\.env|[^/]*\.(pem|key|token|p12|pfx)|id_(rsa|ed25519|ecdsa)[^/]*"
                       r"|ledger\.json[^/]*|credentials[^/]*\.json)$")
MAX_SCAN = 2_000_000


def has_secret(text: str) -> bool:
    """Strict (no opt-out marker): used on anything leaving the Lab (📋 Review packages)."""
    return bool(SECRET_RX.search(text or ""))


def _allowed(root: Path) -> set[str]:
    f = root / ".secretscan-allow"
    if not f.exists():
        return set()
    return {ln.split()[0] for ln in f.read_text().splitlines() if ln.strip() and not ln.startswith("#")}


def _bad(line: str, allow: set[str]) -> bool:
    if ALLOW in line:
        return False
    return any(hashlib.sha256(m.group(0).encode()).hexdigest() not in allow for m in SECRET_RX.finditer(line))


def _git(root: Path, *args: str) -> str:
    r = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, errors="replace",
                       stdin=subprocess.DEVNULL, timeout=120)
    if r.returncode != 0:
        raise RuntimeError(f"git {args[0]} failed: {r.stderr.strip()[:200]}")
    return r.stdout


def scan(root: Path) -> dict:
    root = Path(root).resolve()
    allow = _allowed(root)
    files = sorted(set(_git(root, "ls-files").splitlines()) | set(_git(root, "ls-files", "--others", "--exclude-standard").splitlines()))
    hits: list[dict] = []
    for rel in files:
        if BAD_NAMES.search(rel):
            hits.append({"where": rel, "why": "file name looks like keys or private data"})
            continue
        p = root / rel
        if not p.is_file() or p.is_symlink() or p.stat().st_size > MAX_SCAN:
            continue
        try:
            text = p.read_text(errors="strict")
        except (UnicodeDecodeError, OSError):
            continue                                                  # binary (icons, GIF)
        for n, line in enumerate(text.splitlines(), 1):
            if _bad(line, allow):
                hits.append({"where": f"{rel}:{n}", "why": "looks like a key"})
    commit = ""
    for line in _git(root, "log", "-p", "--all", "--no-color", "--format=@@commit %h").splitlines():
        if line.startswith("@@commit "):
            commit = line.split()[1]
        elif line.startswith("+") and _bad(line, allow):
            hits.append({"where": f"history {commit}", "why": "a commit added something that looks like a key"})
    seen, out = set(), []
    for h in hits:
        if h["where"] not in seen:
            seen.add(h["where"])
            out.append(h)
    return {"ok": not out, "files": len(files), "hits": out[:100]}

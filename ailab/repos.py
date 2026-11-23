"""🔗 Linked code folders (workbench M5, 2026-11-22) — the agent can work on real code such as ~/hermes, propose-only.

Scott links a folder by name (python3 -m ailab link hermes ~/hermes). The agent may then:
  find   — search the folder for text (paths + matching lines only)
  list   — one folder's entries
  pull   — copy files into THIS project under repos/<name>/…  (the text goes to disk, the agent reads what it needs)
  propose — send its changed copies back as HELD changes. Scott sees each as a diff and types apply. The agent never
            writes the real folder.
Never read: dot-folders and dotfiles (.git, .env, .ssh …), key/database files, vendored/third-party trees, anything a
link leads out of the folder, non-text or big files, and any file whose text holds a secret (secretscan).
"""
from __future__ import annotations

import fnmatch
import os
import re
import time
from pathlib import Path

from . import preview, secretscan

NAME_RX = re.compile(r"[a-z0-9][a-z0-9_-]{0,29}")
DENY_DIRS = {"node_modules", "__pycache__", "graphify-out", "site-packages", "dist-packages", "venv", "vault",
             "secrets", "backups", "_to_delete", "tokens"}
DENY_FILE_RX = re.compile(r"(?i)(\.(pem|key|p12|pfx|kdbx|jks|keystore|sqlite3?|db|pyc|lock)$|^id_(rsa|ed25519|ecdsa)"
                          r"|^credentials[^/]*\.json$|^secrets?\.[a-z]+$|\.token$|^tokens?\.json$)")
MAX_FIND, MAX_LIST, MAX_PULL, FIND_SECONDS = 60, 300, 12, 8.0


class RepoError(Exception):
    pass


def linked(cfg: dict) -> dict[str, Path]:
    """name -> folder, only real folders inside the home folder (and never a dot-folder)."""
    out, home = {}, Path.home().resolve()
    for name, raw in (cfg.get("repos") or {}).items():
        if not NAME_RX.fullmatch(str(name)):
            continue
        p = Path(str(raw)).expanduser()
        try:
            rp = p.resolve()
            parts = rp.relative_to(home).parts
        except (OSError, ValueError):
            continue
        if parts and rp.is_dir() and not any(s.startswith(".") for s in parts):
            out[str(name)] = rp
    return out


def programs(cfg: dict) -> dict[str, list[str]]:
    """program -> its linked folders, in the order given (2026-11-22). Folders that are not linked are left out;
    a program left with no folders is dropped. A program only groups — every read rule stays per folder."""
    ok, out = linked(cfg), {}
    for name, members in (cfg.get("programs") or {}).items():
        if not NAME_RX.fullmatch(str(name)) or not isinstance(members, list):
            continue
        m = list(dict.fromkeys(str(x) for x in members if str(x) in ok))
        if m:
            out[str(name)] = m
    return out


def root_of(cfg: dict, name: str) -> Path:
    r = linked(cfg).get(str(name))
    if not r:
        names = ", ".join(sorted(linked(cfg))) or "none"
        raise RepoError(f"No linked code folder called {name!r}. Linked: {names}.")
    return r


def _denied(parts: tuple[str, ...]) -> str:
    for s in parts[:-1]:
        if s.startswith(".") or s in DENY_DIRS:
            return f"the folder {s!r} is never read"
    if parts and (parts[-1].startswith(".") or DENY_FILE_RX.search(parts[-1])):
        return "dotfiles, key files and databases are never read"
    return ""


def safe(root: Path, rel: str) -> Path:
    """A path inside the folder that passes every rule (may not exist yet — a proposed new file)."""
    rel = str(rel or "")
    if not rel or rel.startswith(("/", "~")) or "\\" in rel or ".." in Path(rel).parts:
        raise RepoError(f"{rel!r}: give a path inside the folder, like forge/ailab/card.py.")
    why = _denied(Path(rel).parts)
    if why:
        raise RepoError(f"{rel}: {why}.")
    p, probe = root / rel, root
    for s in Path(rel).parts:
        probe = probe / s
        if probe.is_symlink():
            raise RepoError(f"{rel}: goes through a link — not read.")
    try:
        p.resolve().relative_to(root)
    except (OSError, ValueError):
        raise RepoError(f"{rel}: outside the folder.") from None
    return p


def read_text(root: Path, rel: str) -> str:
    p = safe(root, rel)
    if not p.is_file():
        raise RepoError(f"{rel}: no such file.")
    if p.stat().st_size > preview.MAX_EDIT:
        raise RepoError(f"{rel}: too big to work on here ({p.stat().st_size // 1000} KB; limit {preview.MAX_EDIT // 1000} KB).")
    try:
        text = p.read_bytes().decode("utf-8")
    except UnicodeDecodeError:
        raise RepoError(f"{rel}: not a text file.") from None
    if secretscan.has_secret(text):
        raise RepoError(f"{rel}: holds something that looks like a key or password — never read.")
    return text


def _walk(root: Path, start: Path):
    for d, dirs, files in os.walk(start, followlinks=False):
        dirs[:] = sorted(x for x in dirs if not x.startswith(".") and x not in DENY_DIRS and not (Path(d) / x).is_symlink())
        for f in sorted(files):
            if f.startswith(".") or DENY_FILE_RX.search(f):
                continue
            p = Path(d) / f
            if not p.is_symlink():
                yield p


def ls(root: Path, sub: str = "") -> dict:
    d = safe(root, sub) if sub and sub not in (".", "/") else root
    if sub and _denied(Path(sub).parts + ("x",)):
        raise RepoError(f"{sub}: that folder is never read.")
    if not d.is_dir():
        raise RepoError(f"{sub}: no such folder.")
    dirs, files = [], []
    for p in sorted(d.iterdir()):
        if p.name.startswith(".") or p.is_symlink():
            continue
        if p.is_dir() and p.name not in DENY_DIRS:
            dirs.append(p.relative_to(root).as_posix() + "/")
        elif p.is_file() and not DENY_FILE_RX.search(p.name):
            files.append({"path": p.relative_to(root).as_posix(), "bytes": p.stat().st_size})
    return {"dirs": dirs[:MAX_LIST], "files": files[:MAX_LIST], "truncated": len(dirs) > MAX_LIST or len(files) > MAX_LIST}


def find(root: Path, pattern: str, glob: str = "", sub: str = "") -> dict:
    """Search file text. Returns paths + the matching lines only (no secrets: a file that holds one is skipped whole)."""
    pattern = str(pattern or "")[:200]
    if not pattern:
        raise RepoError("Give a pattern to search for.")
    try:
        rx = re.compile(pattern)
    except re.error:
        rx = re.compile(re.escape(pattern))
    start = safe(root, sub) if sub and sub not in (".", "/") else root
    if sub and _denied(Path(sub).parts + ("x",)):
        raise RepoError(f"{sub}: that folder is never read.")
    out, t0, cut = [], time.monotonic(), False
    for p in _walk(root, start):
        if time.monotonic() - t0 > FIND_SECONDS or len(out) >= MAX_FIND:
            cut = True
            break
        rel = p.relative_to(root).as_posix()
        if glob and not (fnmatch.fnmatch(p.name, glob) or fnmatch.fnmatch(rel, glob)):
            continue
        try:
            if p.stat().st_size > preview.MAX_EDIT:
                continue
            text = p.read_bytes().decode("utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if not rx.search(text) or secretscan.has_secret(text):
            continue
        for i, line in enumerate(text.splitlines(), 1):
            if rx.search(line):
                out.append({"path": rel, "line": i, "text": line.strip()[:200]})
                if len(out) >= MAX_FIND:
                    break
    return {"matches": out, "truncated": cut, **({"tip": "Narrow it: add \"glob\" (e.g. *.py) or \"dir\"."} if cut else {})}


def pull(root: Path, name: str, paths: list, dest_root: Path) -> dict:
    """Copy files into the project at repos/<name>/<path>. Returns names only — the agent reads what it needs."""
    if not isinstance(paths, list) or not paths:
        raise RepoError("paths must be a list of file paths inside the folder.")
    copied, refused = [], []
    for rel in [str(x) for x in paths][:MAX_PULL]:
        try:
            text = read_text(root, rel)
        except RepoError as e:
            refused.append(str(e))
            continue
        dst = dest_root / "repos" / name / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(text)
        copied.append(f"repos/{name}/{rel}")
    more = len(paths) - MAX_PULL
    return {"copied": copied, "refused": refused, **({"note": f"{more} more not copied — at most {MAX_PULL} files per pull."} if more > 0 else {})}

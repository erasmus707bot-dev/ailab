"""Live preview — the project folder is served by a sandboxed process, never by the Lab itself.

The Lab only (a) keeps project files: list, read, Save (user's explicit write, confined to the folder),
(b) talks to `sandbox/pipe_server.py` running under `srt` (no network, reads only the project), and
(c) stores screen captures. If srt is missing the preview says so — it never falls back to running
unsandboxed (AILAB_ALLOW_UNSANDBOXED=1 exists for tests only).
"""
from __future__ import annotations

import base64
import json
import os
import re
import select
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

from . import config

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "hello"
PIPE = Path(__file__).resolve().parent / "sandbox" / "pipe_server.py"
EDIT_EXT = {".html", ".htm", ".css", ".js", ".mjs", ".json", ".svg", ".txt", ".md"}
MAX_EDIT = 500_000
MAX_CAPTURE = 8_000_000
REL = re.compile(r"[A-Za-z0-9_][A-Za-z0-9._-]*(/[A-Za-z0-9_][A-Za-z0-9._-]*)*")
PID = re.compile(r"[a-z0-9-]{1,48}")
TIMEOUT_S = 10


class PreviewError(Exception):
    def __init__(self, message: str, code: str = "preview", icon: str = "👁"):
        super().__init__(message)
        self.message, self.code, self.icon = message, code, icon


def site_dir(pid: str) -> Path:
    if not PID.fullmatch(pid or ""):
        raise PreviewError("Bad project id.", "bad_args", "❓")
    return config.home() / "projects" / pid / "site"


def ensure_site(pid: str) -> Path:
    """New project folder starts as a copy of the fixture so there is always something to see."""
    d = site_dir(pid)
    if not d.exists():
        d.parent.mkdir(parents=True, exist_ok=True)
        tmp = d.parent / ".site-new"
        shutil.rmtree(tmp, ignore_errors=True)                       # our own half-made copy only
        shutil.copytree(FIXTURE, tmp)
        os.replace(tmp, d)
    return d


def _path(pid: str, rel: str, *, editing: bool = True) -> Path:
    root = ensure_site(pid).resolve()
    if not rel or not REL.fullmatch(rel) or ".." in rel.split("/"):
        raise PreviewError("That file name isn't allowed.", "bad_args", "❓")
    if editing and Path(rel).suffix.lower() not in EDIT_EXT:
        raise PreviewError(f"Only {' '.join(sorted(EDIT_EXT))} files can be edited here.", "bad_args", "❓")
    p = root / rel
    if not p.parent.resolve().is_relative_to(root) or (p.is_symlink()):
        raise PreviewError("That file is outside the project folder.", "outside", "🚧")
    return p


def list_files(pid: str) -> list[dict]:
    return list_root(ensure_site(pid))


def list_root(root: Path) -> list[dict]:
    root, out = Path(root), []
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root).as_posix()
        if p.is_file() and not p.is_symlink() and not any(s.startswith(".") for s in rel.split("/")):
            out.append({"path": rel, "bytes": p.stat().st_size, "editable": p.suffix.lower() in EDIT_EXT})
        if len(out) >= 500:
            break
    return out


def read_file(pid: str, rel: str) -> str:
    p = _path(pid, rel)
    if not p.is_file():
        raise PreviewError("No such file.", "not_found", "❓")
    if p.stat().st_size > MAX_EDIT:
        raise PreviewError("File is too big to edit here.", "too_big", "📦")
    return p.read_text(errors="replace")


def save_file(pid: str, rel: str, text: str) -> dict:
    """Explicit 💾 Save. Atomic, inside the project folder only."""
    if len(text.encode()) > MAX_EDIT:
        raise PreviewError("File is too big to save here.", "too_big", "📦")
    p = _path(pid, rel)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(f".{p.name}.saving")
    tmp.write_text(text)
    os.replace(tmp, p)
    return {"ok": True, "path": rel, "bytes": p.stat().st_size, "at": time.time()}


def save_capture(pid: str, data_url: str) -> dict:
    m = re.fullmatch(r"data:image/png;base64,([A-Za-z0-9+/=]+)", data_url or "")
    if not m:
        raise PreviewError("Capture must be a PNG.", "bad_args", "❓")
    raw = base64.b64decode(m.group(1))
    if len(raw) > MAX_CAPTURE or raw[:8] != b"\x89PNG\r\n\x1a\n":
        raise PreviewError("Capture is not a usable PNG.", "bad_args", "❓")
    ensure_site(pid)
    d = site_dir(pid).parent / "captures"
    d.mkdir(exist_ok=True)
    f = d / time.strftime("capture-%Y%m%d-%H%M%S.png")
    n = 2
    while f.exists():
        f, n = d / time.strftime(f"capture-%Y%m%d-%H%M%S-{n}.png"), n + 1
    f.write_bytes(raw)
    return {"ok": True, "file": f.name, "bytes": len(raw)}


# ---------------------------------------------------------------- sandbox
def sandbox_kind() -> str:
    if os.environ.get("AILAB_ALLOW_UNSANDBOXED") == "1":
        return "none"
    return "srt" if shutil.which("srt") else "missing"


def _prefix(exe: str | None) -> Path | None:
    """Install folder of a program (srt, node, python) — needed when it lives under $HOME (~/.npm-global, nvm)."""
    if not exe:
        return None
    r = Path(exe).resolve()
    parts = r.parts
    if "node_modules" in parts:                         # …/<prefix>/lib/node_modules/@scope/pkg/dist/cli.js
        i = parts.index("node_modules")
        return Path(*parts[:max(i - 1, 1)])
    return r.parent.parent                              # …/<prefix>/bin/node


def runtime_reads() -> list[str]:
    home, out = Path.home().resolve(), []
    for exe in (shutil.which("srt"), shutil.which("node"), sys.executable):
        pre = _prefix(exe)
        if pre and pre.is_relative_to(home) and pre != home:
            out.append(str(pre))
    for pre in {Path(sys.prefix).resolve(), Path(sys.base_prefix).resolve()}:
        if pre.is_relative_to(home) and pre != home:
            out.append(str(pre))
    return sorted(set(out))


def srt_settings(root: Path, scratch: Path | None = None) -> dict:
    """$HOME unreadable except the project, the pipe script and the runtimes' own install folders.
    Writes only to an empty per-sandbox scratch dir (srt needs one); no network."""
    return {"network": {"allowedDomains": [], "deniedDomains": []},
            "filesystem": {"denyRead": [str(Path.home()), "/etc/ssh", "/root"],
                           "allowRead": [str(root), str(PIPE.parent), *runtime_reads()],
                           "allowWrite": [str(scratch)] if scratch else [], "denyWrite": [str(root)]}}


class Sandbox:
    """One pipe server per project, started on first use, restarted if it dies."""

    def __init__(self, pid: str, root: Path | None = None):
        """pid = sandbox key; root given = a ⚖️ Compare lane copy (M8), else the project's site."""
        self.pid, self.root = pid, (Path(root) if root else ensure_site(pid)).resolve()
        self.proc: subprocess.Popen | None = None
        self.lock = threading.Lock()
        self.kind = sandbox_kind()

    def _start(self) -> None:
        if self.kind == "missing":
            raise PreviewError("The sandbox (srt) isn't installed, so the preview won't run code. "
                               "Nothing ran outside the sandbox.", "no_sandbox", "🧱")
        cmd = [sys.executable, "-I", "-B", str(PIPE), str(self.root)]
        cwd = tempfile.mkdtemp(prefix="ailab-", dir="/tmp")      # short path: srt bridge sockets
        if self.kind == "srt":
            run = config.home() / "run"
            run.mkdir(parents=True, exist_ok=True)
            cfg = run / f"srt-{self.pid}.json"
            cfg.write_text(json.dumps(srt_settings(self.root, Path(cwd))))
            cmd = ["srt", "-s", str(cfg), *cmd]
        self.proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                     cwd=cwd, text=True, bufsize=1, start_new_session=True)

    def ask(self, req: dict) -> dict:
        with self.lock:
            for attempt in (1, 2):
                if self.proc is not None and self.proc.poll() is not None:
                    self._stop()                                    # reap the rest of a dead group
                if self.proc is None:
                    self._start()
                try:
                    self.proc.stdin.write(json.dumps(req) + "\n")
                    self.proc.stdin.flush()
                    ready, _, _ = select.select([self.proc.stdout], [], [], TIMEOUT_S)
                    line = self.proc.stdout.readline() if ready else ""
                except (BrokenPipeError, OSError):
                    line = ""
                if line:
                    return json.loads(line)
                err = self._stop()
                if attempt == 2:
                    raise PreviewError("The sandboxed preview didn't answer." + (f" ({err})" if err else ""),
                                       "sandbox_failed", "🧱")
        return {}

    def _stop(self) -> str:
        """Close stdin (the pipe server exits on EOF), then kill the whole group: srt + bwrap + python."""
        p, self.proc, err = self.proc, None, ""
        if not p:
            return err
        try:
            p.stdin.close()
        except OSError:
            pass
        try:
            p.wait(timeout=2)
        except subprocess.TimeoutExpired:
            pass
        try:
            os.killpg(p.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
        p.wait(timeout=5)
        try:
            if select.select([p.stderr], [], [], 0.5)[0]:
                lines = (p.stderr.read() or "").strip().splitlines()
                err = lines[-1][:200] if lines else ""
        except (OSError, ValueError):
            err = ""
        return err

    def close(self) -> None:
        with self.lock:
            self._stop()


class Preview:
    def __init__(self):
        self.boxes: dict[str, Sandbox] = {}
        self.lock = threading.Lock()

    def box(self, pid: str, root: Path | None = None) -> Sandbox:
        with self.lock:
            if pid not in self.boxes:
                self.boxes[pid] = Sandbox(pid, root)
            return self.boxes[pid]

    def get(self, pid: str, rel: str, root: Path | None = None) -> tuple[int, str, bytes]:
        r = self.box(pid, root).ask({"op": "get", "path": rel})
        if not r.get("ok"):
            return int(r.get("status") or 404), "text/plain; charset=utf-8", b"Not found in this project."
        return 200, r["ctype"], base64.b64decode(r["b64"])

    def version(self, pid: str) -> str:
        return self.box(pid).ask({"op": "version"}).get("v", "")

    def doctor(self, pid: str = "scratch") -> dict:
        """One-shot health check: start the sandbox, fetch index.html, report the real error if any."""
        b = self.box(pid)
        try:
            r = b.ask({"op": "get", "path": "index.html"})
            return {"ok": bool(r.get("ok")), "sandbox": b.kind, "status": r.get("status"), "reads": runtime_reads()}
        except PreviewError as e:
            return {"ok": False, "sandbox": b.kind, "error": e.message, "reads": runtime_reads()}

    def status(self, pid: str) -> dict:
        b = self.box(pid)
        return {"sandbox": b.kind, "root": str(b.root)}

    def close(self) -> None:
        for b in list(self.boxes.values()):
            b.close()

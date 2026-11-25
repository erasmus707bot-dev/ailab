"""🛡 Guard link (2026-11-24): the Lab may change its own code (~/ailab) and Hermes (~/hermes) — only behind the Guard.

Scott's rules: the Lab is walled off from the rollback tool (the Guard runs as root at 127.0.0.1:8860; the Lab can only
ask it things), and Scott taps ✅ for every change. A guarded apply goes:

  1. 🧪 prove  — a trial copy of the program (git-tracked files) + the changes, tests run inside the srt sandbox
                 (no network, writes only in the trial copy). New code never runs outside the sandbox before step 4.
                 Tests that already failed before the change don't block it (the same tests are run on a clean copy).
  2. 🛡 copy   — the Guard saves a copy. Guard not answering → nothing is written.
  3. 👀 watch  — the Guard starts watching (it goes back by itself if the program stops answering).
  4. ✍️ write  — the files go in; a half-done write is put back from the copy straight away.
  5. 🔄 restart — through the Guard (gandalf can't restart Hermes), after this reply has gone out.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import threading
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

from . import config

GUARD_PATH_PARTS = ("ailab-guard",)          # the Guard's own source folder is never written from the Lab
MAX_TRIAL_FILE = 20 * 1024 * 1024
TEST_TIMEOUT_S = 900


class GuardDown(Exception):
    pass


class ProofFailed(Exception):
    def __init__(self, message: str, checks: list[dict]):
        super().__init__(message)
        self.checks = checks


# ------------------------------------------------------------------ which program a file belongs to
def guarded(cfg: dict) -> dict[str, Path]:
    out = {}
    for name, raw in (cfg.get("guarded") or {}).items():
        try:
            out[str(name)] = Path(str(raw)).expanduser().resolve()
        except OSError:
            continue
    return out


def program_of(cfg: dict, target: Path) -> tuple[str, Path] | None:
    t = Path(os.path.normpath(target))
    for name, root in guarded(cfg).items():
        try:
            t.relative_to(root)
            return name, root
        except ValueError:
            continue
    return None


def is_guard_path(target: Path) -> bool:
    return any(p in GUARD_PATH_PARTS for p in Path(target).parts)


# ------------------------------------------------------------------ talking to the Guard (127.0.0.1 only)
def _call(cfg: dict, path: str, body: dict | None = None, timeout: float = 120) -> dict:
    url = str(cfg.get("guard_url") or "http://127.0.0.1:8860").rstrip("/") + path
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, method="POST" if data else "GET",
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310 — loopback guard
            j = json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            j = json.loads(e.read() or b"{}")
        except ValueError:
            j = {"ok": False, "error": f"HTTP {e.code}"}
    except Exception as e:  # noqa: BLE001
        raise GuardDown(f"The 🛡 Guard isn't answering ({type(e).__name__}) — nothing was written.") from e
    if not j.get("ok", True):
        raise GuardDown(f"The 🛡 Guard said no: {j.get('error') or 'unknown'} — nothing was written.")
    return j


def state(cfg: dict) -> dict:
    try:
        return {"ok": True, "up": True, **_call(cfg, "/api/state", timeout=8)}
    except GuardDown as e:
        return {"ok": True, "up": False, "why": str(e), "targets": []}


def snap(cfg: dict, name: str, why: str) -> str:
    return _call(cfg, "/api/snap", {"target": name, "why": why[:280], "by": "lab"})["id"]


def watch(cfg: dict, name: str, snap_id: str, why: str) -> dict:
    return _call(cfg, "/api/watch", {"target": name, "snap": snap_id, "why": why[:180],
                                     "minutes": cfg.get("guard_watch_minutes") or 5})


def restore(cfg: dict, name: str, snap_id: str) -> dict:
    return _call(cfg, "/api/restore", {"target": name, "snap": snap_id, "confirm": "restore", "by": "lab"}, timeout=300)


def restart_later(cfg: dict, name: str, delay: float = 1.5) -> None:
    """After this reply has gone out — restarting the Lab mid-reply would cut the reply off."""
    def go():
        time.sleep(delay)
        try:
            _call(cfg, "/api/restart", {"target": name}, timeout=120)
        except GuardDown:
            pass                                    # the watch is already running; a missed restart is visible there
    threading.Thread(target=go, daemon=True).start()


# ------------------------------------------------------------------ 🧪 proof in a trial copy
def tracked(root: Path) -> list[str]:
    r = subprocess.run(["git", "-C", str(root), "ls-files", "-co", "--exclude-standard", "-z"],
                       capture_output=True, timeout=120)
    if r.returncode != 0:
        raise ProofFailed("git couldn't list the program's files.", [])
    return [n for n in r.stdout.decode(errors="surrogateescape").split("\0") if n]


def trial_copy(root: Path, changes: dict[str, str], dest: Path) -> Path:
    dest.mkdir(parents=True, exist_ok=True)
    for rel in tracked(root):
        src = root / rel
        out = dest / rel
        if os.path.islink(src):
            continue                                 # links are left out of a trial copy
        try:
            if not src.is_file() or src.stat().st_size > MAX_TRIAL_FILE:
                continue
        except OSError:
            continue
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, out)
    for rel, text in changes.items():
        out = dest / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text)
    if (root / ".git").exists():                     # some tests read git; a fresh repo is enough
        subprocess.run(["git", "init", "-q", str(dest)], capture_output=True, timeout=30)
    return dest


def checks_for(name: str, trial: Path, changed: list[str]) -> list[tuple[str, str]]:
    """(label, shell command) — run inside the trial copy, in the sandbox."""
    out: list[tuple[str, str]] = []
    py = [c for c in changed if c.endswith(".py")]
    js = [c for c in changed if c.endswith((".js", ".mjs"))]
    js_in_html = [c for c in changed if c.endswith((".html", ".htm"))]
    js_files = " ".join(f"'{c}'" for c in js)
    if py:
        out.append(("🐍 Python reads cleanly", "python3 -m py_compile " + " ".join(f"'{c}'" for c in py)))
    if js and shutil.which("node"):
        out.append(("📜 JavaScript reads cleanly", f"for f in {js_files}; do node --check \"$f\" || exit 1; done"))
    for c in [c for c in changed if c.endswith(".json")]:
        out.append((f"🧾 {c} is valid JSON", f"python3 -c \"import json,sys; json.load(open(sys.argv[1]))\" '{c}'"))
    if name == "ailab":
        out.append(("🧪 every Lab test", "AILAB_HOME=\"$PWD/.labhome\" python3 -m pytest -q -x -p no:cacheprovider tests"))
        out.append(("🚀 the Lab starts", "AILAB_HOME=\"$PWD/.labhome\" python3 -c \"import ailab.server\""))
    else:
        stems = {Path(c).stem for c in py + js + js_in_html}
        tests: list[str] = []
        for st in sorted(stems):
            for t in trial.glob(f"**/tests/test_{st}*.py"):
                if "node_modules" not in t.parts:
                    tests.append(str(t.relative_to(trial)))
        tests = sorted(set(tests))[:15]
        if tests:
            out.append((f"🧪 {len(tests)} matching test file(s)", "python3 -m pytest -q -x -p no:cacheprovider "
                        + " ".join(f"'{t}'" for t in tests)))
    return out


def _sandbox_run(root: Path, cmd: str) -> dict:
    from . import agent
    return agent.run_in_sandbox(root, cmd, timeout=TEST_TIMEOUT_S)


def prove(cfg: dict, name: str, root: Path, changes: dict[str, str], runner=None) -> list[dict]:
    """Run the checks. Raises ProofFailed (with the check list) when a check fails that didn't fail before."""
    runner = runner or _sandbox_run
    base = config.files_home() / "_trial"
    tid = time.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6]
    trial = trial_copy(root, changes, base / tid)
    clean: Path | None = None
    results: list[dict] = []
    try:
        for label, cmd in checks_for(name, trial, sorted(changes)):
            r = runner(trial, cmd)
            ok = r.get("exit") == 0
            row = {"check": label, "ok": ok, "tail": (r.get("output") or "")[-1500:]}
            if not ok and "every Lab test" not in label and "matching test" not in label:
                results.append(row)
                raise ProofFailed(f"{label} — failed.", results)
            if not ok:                                # did these tests already fail before the change?
                if clean is None:
                    clean = trial_copy(root, {}, base / (tid + "-before"))
                rb = runner(clean, cmd)
                if rb.get("exit") == 0:
                    results.append(row)
                    raise ProofFailed(f"{label} — the change broke them (they passed before).", results)
                row.update(ok=True, note="these tests already failed before the change — not caused by it")
            results.append(row)
        return results
    finally:
        shutil.rmtree(trial, ignore_errors=True)
        if clean:
            shutil.rmtree(clean, ignore_errors=True)

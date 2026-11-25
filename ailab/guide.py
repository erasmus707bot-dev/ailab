"""🧭 Errors that say what to do next (2026-11-25, Scott: "make it so errors guide me to make the correction needed").

explain(e) → one plain message in three parts:  what went wrong · whose fault (the Lab's code / a connection / a file /
the request) · 👉 the next step to take. The full technical trace goes to <lab home>/errors.log, never on screen.
Errors that already carry their own fix (HermesRefused, SpendBlocked, PrivacyRefused, PreviewError) don't come here."""
from __future__ import annotations

import errno
import time
import traceback
from pathlib import Path

from . import config

PKG = Path(__file__).resolve().parent
BUGS = (NameError, AttributeError, TypeError, KeyError, IndexError, ImportError, UnboundLocalError, AssertionError,
        ZeroDivisionError, RecursionError, NotImplementedError)
LOG_MAX = 400_000


def log_file() -> Path:
    return config.home() / "errors.log"


def spot(e: BaseException) -> tuple[str, int, str]:
    """(file, line, function) of the deepest frame inside the Lab's own code — ('', 0, '') if none."""
    hit = ("", 0, "")
    for f in traceback.extract_tb(e.__traceback__):
        try:
            rel = Path(f.filename).resolve().relative_to(PKG.parent)
        except ValueError:
            continue
        hit = (str(rel), int(f.lineno or 0), f.name)
    return hit


def _log(e: BaseException, where: str) -> str:
    try:
        f = log_file()
        f.parent.mkdir(parents=True, exist_ok=True)
        if f.exists() and f.stat().st_size > LOG_MAX:
            f.write_text(f.read_text(errors="replace")[-LOG_MAX // 2:])
        with f.open("a") as fh:
            fh.write(f"\n== {time.strftime('%F %T')} · {where}\n" + "".join(traceback.format_exception(type(e), e, e.__traceback__)))
        return str(f).replace(str(Path.home()), "~")
    except OSError:
        return ""


def explain(e: BaseException, where: str = "") -> str:
    name, msg = type(e).__name__, " ".join(str(e).split())[:200]
    file, line, fn = spot(e)
    at = f"{file} line {line}" if file else ""
    log = _log(e, where)
    saved = f" Details saved in {log}." if log else ""
    low = msg.lower()
    if isinstance(e, (ConnectionError, TimeoutError)) or any(w in low for w in (
            "urlopen error", "connection refused", "timed out", "name or service not known", "temporary failure",
            "eof occurred", "connection reset", "remote end closed")):
        local = any(w in low for w in ("127.0.0.1", "localhost", "refused"))
        return (f"🔌 A connection dropped — {msg or name}. Your words are fine. 👉 "
                + ("Hermes (or the local picture service) isn't answering: check it's running, then press ▶ Start again."
                   if local else "Check the internet, wait a minute, then press ▶ Start again — nothing was charged for this step.")
                + saved)
    if isinstance(e, FileNotFoundError):
        return (f"📁 A file the Lab needed isn't there — {msg}. 👉 If you moved or deleted it, put it back (📍 shows where "
                f"this project's files live); otherwise press ▶ Start again to remake it." + saved)
    if isinstance(e, PermissionError):
        return (f"🔒 The Lab isn't allowed to write there — {msg}. 👉 On gandalf, fix the folder's owner: "
                f"sudo chown -R $USER ~/hermes-data/ailab — then press ▶ Start again." + saved)
    if isinstance(e, OSError) and e.errno in (errno.ENOSPC, errno.EDQUOT):
        return ("💾 The disk is full. 👉 Free some room (Hermes → 🧹 Housekeeping, or delete old clips in this project's "
                "videos/ folder), then press ▶ Start again." + saved)
    if isinstance(e, MemoryError) or "out of memory" in low:
        return (f"🧠 This computer ran out of memory — {msg or name}. 👉 Close other heavy things (a local model, a game), "
                "or pick a smaller model / shorter clip, then press ▶ Start again." + saved)
    if isinstance(e, BUGS):
        ask = f"Fix {name}: {msg}" + (f" in {at} ({fn})" if at else "")
        return (f"🐞 The Lab's own code broke — not your words, not the model ({name}: {msg}"
                + (f", at {at}" if at else "") + "). 👉 Nothing for you to reword. Press 🛠 Change ailab and paste: \""
                + ask + "\" — or give that line to Claude. Then press ▶ Start again." + saved)
    return (f"⚠️ Something went wrong the Lab doesn't have a fix written for — {name}: {msg}"
            + (f" (at {at})" if at else "") + ". 👉 Press ▶ Start again once; if it fails the same way, give Claude this "
            "message" + (f" and {log}" if log else "") + ".")

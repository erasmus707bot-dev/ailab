"""🧠 Lab memory (2026-11-24, build prompt BUILD_PROMPT_2026-11-24_ai-lab-memory-prompt-builder.md, M1).

What the Lab knows about Scott, as one .md per subject in ~/.config/ailab/memory/ (same layout as Claude memory):

    ---
    name: rules-hermes
    description: one line
    updated: 2026-11-24T06:10
    ---
    - [claude-import] fact            ← copied from his Claude setup (re-import replaces these)
    - [lab] fact                      ← the Lab saved it from a session (M2)
    - [scott] fact                    ← Scott added it himself — the only way sensitive info gets in

Rules (Scott, 2026-11-23): saves automatically; NEVER auto-saves sensitive info (keys, health, money, identity) —
only Scott adds that by hand. Import COPIES his Claude setup and never edits the source files.
Every change is logged (before/after) so it can be undone.
"""
from __future__ import annotations

import fcntl
import json
import re
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

from . import config
from .secretscan import SECRET_RX

SOURCES = ("claude-import", "lab", "scott")
MAX_FILE = 60_000                     # bytes read per source file
MAX_LINE = 400
LINE_RX = re.compile(r"^- \[(claude-import|lab|scott)\] (.+)$")

# Sensitive = never saved automatically. Broad on purpose: a false skip costs one hand-add; a false save leaks.
SENSITIVE: dict[str, re.Pattern] = {
    "secret": re.compile(SECRET_RX.pattern + r"|\b(password|passwd|passcode|api[_ -]?key|secret[_ -]?key|private key)\s*[:=]",
                         re.I),
    "id-number": re.compile(r"\b\d{3}-\d{2}-\d{4}\b|\b(?:\d[ -]?){13,19}\b|\b(ssn|social security|passport|driver'?s licen[cs]e)\b",
                            re.I),
    "health": re.compile(r"\b(diagnos\w*|autis\w*|adhd|depress\w*|anxiety|bipolar|medication|prescri\w*|therap(y|ist)|"
                         r"psychiatr\w*|disorder\b|allerg\w*|cancer|diabet\w*|surgery|blood pressure|mental health|insulin|"
                         r"illness|chronic|symptom\w*|health condition)", re.I),
    "money": re.compile(r"\b(salary|income|net worth|account balance|bank account|routing number|credit score|"
                        r"debts?\b|loan balance|paycheck|savings of)", re.I),
    "identity": re.compile(r"\b(religio\w*|sexual orientation|gay|lesbian|bisexual|transgender|ethnicit\w*|immigra\w*|"
                           r"political (party|views?)|union member)", re.I),
}


class MemError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code, self.message = code, message


def root() -> Path:
    d = config.home() / "memory"
    d.mkdir(parents=True, exist_ok=True)
    return d


@contextmanager
def _lock():
    with open(root() / ".lock", "w") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


def slug(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")[:60]
    if not s:
        raise MemError("bad_name", "A memory subject needs a name.")
    return s


def sensitive(text: str) -> str:
    """Which sensitive kind a line is ('' = safe to save automatically)."""
    for kind, rx in SENSITIVE.items():
        if rx.search(text or ""):
            return kind
    return ""


# ---- one subject file ------------------------------------------------------------------------------------------
def _path(name: str) -> Path:
    return root() / f"{slug(name)}.md"


def parse(text: str) -> dict:
    meta, lines, body = {}, [], text or ""
    if body.startswith("---\n") and "\n---" in body[4:]:
        head, body = body[4:].split("\n---", 1)
        for ln in head.splitlines():
            if ":" in ln:
                k, v = ln.split(":", 1)
                meta[k.strip()] = v.strip()
    for ln in body.splitlines():
        m = LINE_RX.match(ln.strip())
        if m:
            lines.append({"source": m.group(1), "text": m.group(2)})
    return {"meta": meta, "lines": lines}


def render(name: str, description: str, lines: list[dict]) -> str:
    head = f"---\nname: {slug(name)}\ndescription: {description.strip()[:160]}\nupdated: {time.strftime('%Y-%m-%dT%H:%M')}\n---\n"
    return head + "".join(f"- [{l['source']}] {l['text']}\n" for l in lines)


def read(name: str) -> dict:
    p = _path(name)
    if not p.exists():
        raise MemError("not_found", f"No memory subject called {name!r}.")
    d = parse(p.read_text(errors="replace"))
    return {"name": slug(name), "description": d["meta"].get("description", ""), "updated": d["meta"].get("updated", ""),
            "lines": d["lines"]}


def subjects() -> list[dict]:
    out = []
    for p in sorted(root().glob("*.md")):
        d = parse(p.read_text(errors="replace"))
        src = {s: sum(1 for l in d["lines"] if l["source"] == s) for s in SOURCES}
        out.append({"name": p.stem, "description": d["meta"].get("description", ""), "updated": d["meta"].get("updated", ""),
                    "count": len(d["lines"]), "by_source": src})
    return out


def _log(name: str, before: str | None, after: str | None, why: str) -> str:
    wid = uuid.uuid4().hex[:12]                       # each write has an id, so ↶ can undo exactly one review (2026-11-24)
    with open(root() / "changes.jsonl", "a") as fh:
        fh.write(json.dumps({"t": time.time(), "id": wid, "name": name, "why": why, "before": before, "after": after}) + "\n")
    return wid


def _write(name: str, text: str | None, why: str) -> str | None:
    p = _path(name)
    before = p.read_text(errors="replace") if p.exists() else None
    if before == text:
        return None
    if text is None:
        p.rename(p.with_suffix(".md.removed"))       # deleting is off in Scott's folders; keep it recoverable
    else:
        p.write_text(text)
    return _log(slug(name), before, text, why)


def write_subject(name: str, description: str, lines: list[dict], why: str = "edit", ids: list | None = None) -> dict:
    """ids: if given, the id of this write is appended (None = nothing changed)."""
    clean = []
    for l in lines:
        t = re.sub(r"\s+", " ", str(l.get("text") or "")).strip()[:MAX_LINE]
        s = l.get("source") if l.get("source") in SOURCES else "scott"
        if t:
            clean.append({"source": s, "text": t})
    with _lock():
        wid = _write(name, render(name, description, clean), why)
    if ids is not None and wid:
        ids.append(wid)
    return read(name)


def add_fact(name: str, text: str, source: str = "lab", description: str = "") -> dict:
    """Add one fact. Automatic saves (source lab/claude-import) skip sensitive lines; Scott's own adds do not."""
    text = re.sub(r"\s+", " ", text or "").strip()[:MAX_LINE]
    if not text:
        return {"saved": False, "why": "empty"}
    if source != "scott":
        kind = sensitive(text)
        if kind:
            return {"saved": False, "why": f"sensitive:{kind}"}
    with _lock():
        p = _path(name)
        cur = parse(p.read_text(errors="replace")) if p.exists() else {"meta": {}, "lines": []}
        if any(l["text"].lower() == text.lower() for l in cur["lines"]):
            return {"saved": False, "why": "already known"}
        desc = description or cur["meta"].get("description") or name.replace("-", " ")
        _write(name, render(name, desc, cur["lines"] + [{"source": source, "text": text}]), f"add:{source}")
    return {"saved": True, "name": slug(name)}


def undo_last() -> dict:
    f = root() / "changes.jsonl"
    rows = [json.loads(x) for x in f.read_text().splitlines() if x.strip()] if f.exists() else []
    if not rows:
        raise MemError("nothing", "Nothing to undo.")
    last = rows[-1]
    with _lock():
        p = _path(last["name"])
        if last["before"] is None:
            if p.exists():
                p.rename(p.with_suffix(".md.removed"))
        else:
            p.write_text(last["before"])
        f.write_text("".join(json.dumps(r) + "\n" for r in rows[:-1]))
    return {"undone": last["name"], "why": last["why"]}


def undo_ids(ids: list[str]) -> dict:
    """↶ exactly these writes (one review's apply) — not whatever was written last.
    Refused, with nothing touched, if a subject changed again since (its file is no longer that write's result)."""
    want = [str(i) for i in ids if str(i).strip()][:200]
    if not want:
        raise MemError("nothing", "Nothing to undo.")
    f = root() / "changes.jsonl"
    with _lock():
        rows = [json.loads(x) for x in f.read_text().splitlines() if x.strip()] if f.exists() else []
        hit = [r for r in rows if r.get("id") in set(want)]
        if len(hit) != len(set(want)):
            raise MemError("gone", "That change was already undone.")
        for r in hit:
            p = _path(r["name"])
            now = p.read_text(errors="replace") if p.exists() else None
            if now != r["after"]:
                raise MemError("changed", f"“{r['name']}” changed since — undo that on the Memory page first. Nothing was undone.")
        for r in reversed(hit):
            p = _path(r["name"])
            if r["before"] is None:
                if p.exists():
                    p.rename(p.with_suffix(".md.removed"))
            else:
                p.write_text(r["before"])
        f.write_text("".join(json.dumps(r) + "\n" for r in rows if r.get("id") not in set(want)))
    return {"undone": sorted({r["name"] for r in hit}), "count": len(hit)}


def search(q: str, limit: int = 50) -> list[dict]:
    q = (q or "").lower().strip()
    out = []
    for s in subjects():
        for l in read(s["name"])["lines"]:
            if not q or q in l["text"].lower() or q in s["name"]:
                out.append({"name": s["name"], **l})
                if len(out) >= limit:
                    return out
    return out


# ---- import from Scott's Claude setup ----------------------------------------------------------------------
def import_sources(home: Path | None = None) -> list[tuple[str, str, Path]]:
    """(subject, description, file) for every part of his Claude setup that exists on this machine."""
    h = home or Path.home()
    out: list[tuple[str, str, Path]] = []
    for proj in ("hermes", "ailab", "hermes-local", "hermes-forge"):
        p = h / proj / "CLAUDE.md"
        if p.exists():
            out.append((f"rules-{proj}", f"Scott's Claude rules for ~/{proj} (CLAUDE.md)", p))
    if (h / ".claude/CLAUDE.md").exists():
        out.append(("rules-claude-code", "Scott's global Claude Code rules (~/.claude/CLAUDE.md)", h / ".claude/CLAUDE.md"))
    for p in sorted((h / ".claude/skills").glob("*/SKILL.md")) if (h / ".claude/skills").exists() else []:
        out.append((f"skill-{p.parent.name}", f"Claude skill {p.parent.name} (~/.claude/skills)", p))
    for p in sorted(h.glob("*/rules.md")):
        out.append((f"rules-md-{p.parent.name}", f"rules.md in ~/{p.parent.name}", p))
    if (h / "hermes/SESSION-LEDGER.md").exists():
        out.append(("hermes-ledger-rules", "Hermes SESSION-LEDGER section 1 (how sessions must work)",
                    h / "hermes/SESSION-LEDGER.md"))
    exp = h / "hermes-data/claude-memory-export"
    for p in sorted(exp.glob("*.md")) if exp.exists() else []:
        out.append((f"claude-{p.stem}", "", p))           # description comes from the export's own frontmatter
    return out


def _facts(text: str, ledger: bool = False) -> tuple[list[str], str]:
    """Plain fact lines from a markdown file (+ its frontmatter description if any)."""
    desc = ""
    if text.startswith("---\n") and "\n---" in text[4:]:
        head, text = text[4:].split("\n---", 1)
        for ln in head.splitlines():
            if ln.startswith("description:"):
                desc = ln.split(":", 1)[1].strip()
    if ledger:                                            # section 1 only — the rest is history, not instruction
        m = re.split(r"\n## ", text)
        text = m[1] if len(m) > 1 else text
    out, fence = [], False
    for ln in text.splitlines():
        s = ln.strip()
        if s.startswith("```"):
            fence = not fence
            continue
        if fence or not s or s.startswith(("<!--", "|---", "---")) or re.fullmatch(r"#+.*", s) and len(s) < 4:
            continue
        s = re.sub(r"^[-*>]\s+|^\d+\.\s+", "", s)
        s = re.sub(r"^\[(stated|observed|inferred)\]\s*", "", s)
        s = re.sub(r"\s*\[s:[^\]]*\]$", "", s)
        s = s.lstrip("#").strip()
        if len(s) >= 3:
            out.append(s[:MAX_LINE])
    return out, desc


def import_all(home: Path | None = None) -> dict:
    """Copy his Claude setup into Lab memory. Replaces only earlier [claude-import] lines; Lab/Scott lines stay.
    Runs twice = same result. Sensitive lines are skipped and only COUNTED (never shown)."""
    report = {"subjects": [], "added": 0, "skipped": {}, "unchanged": 0}
    for name, desc, path in import_sources(home):
        try:
            raw = path.read_bytes()[:MAX_FILE].decode("utf-8", "replace")
        except OSError:
            continue
        facts, fdesc = _facts(raw, ledger=name == "hermes-ledger-rules")
        keep = []
        for f in facts:
            kind = sensitive(f)
            if kind:
                report["skipped"][kind] = report["skipped"].get(kind, 0) + 1
            elif f.lower() not in {k.lower() for k in keep}:
                keep.append(f)
        with _lock():
            p = _path(name)
            cur = parse(p.read_text(errors="replace")) if p.exists() else {"meta": {}, "lines": []}
            own = [l for l in cur["lines"] if l["source"] != "claude-import"]
            own_txt = {l["text"].lower() for l in own}
            lines = [{"source": "claude-import", "text": f} for f in keep if f.lower() not in own_txt] + own
            text = render(name, desc or fdesc or cur["meta"].get("description") or name, lines)
            if p.exists() and parse(p.read_text())["lines"] == lines:
                report["unchanged"] += 1
            else:
                _write(name, text, "import")
                report["added"] += len(keep)
        report["subjects"].append(slug(name))
    return report


# ---- what the agent gets (M2) ------------------------------------------------------------------------------
ALWAYS = ("claude-profile", "claude-preferences", "rules-claude-code")


def for_context(project: str = "", ask: str = "", budget_chars: int = 6000) -> tuple[str, list[str]]:
    """A short memory block for the model + the subject names used (shown to Scott as "used: …")."""
    names = [s["name"] for s in subjects()]
    words = {w for w in re.findall(r"[a-z0-9]{4,}", f"{project} {ask}".lower())}
    pick = [n for n in ALWAYS[:2] if n in names]          # who he is + how he wants things first
    for w in re.findall(r"[a-z0-9-]+", (project or "").lower()):   # then that program's own rules (before the long global file)
        if f"rules-{w}" in names and f"rules-{w}" not in pick:
            pick.append(f"rules-{w}")
    pick += [n for n in ALWAYS[2:] if n in names]
    scored = sorted(((sum(w in n for w in words), n) for n in names if n not in pick), reverse=True)
    pick += [n for sc, n in scored if sc > 0][:4]
    out, used, size = [], [], 0
    for n in pick:
        lines = [l["text"] for l in read(n)["lines"]]
        block = f"## {n}\n" + "\n".join(f"- {t}" for t in lines)
        if size + len(block) > budget_chars:
            block = block[: max(0, budget_chars - size)]
        if not block.strip():
            break
        out.append(block)
        used.append(n)
        size += len(block)
        if size >= budget_chars:
            break
    return ("What you know about Scott (from his Lab memory):\n" + "\n\n".join(out)) if out else "", used


# ---- auto-save what Scott states (M2) ---------------------------------------------------------------------------
# Only his own durable statements about how he wants things ("I prefer…", "always…", "never…", "from now on…").
# A guess at intent is never saved; sensitive lines never are. Goes to the "lab-learned" subject, tagged [lab].
STATED_RX = re.compile(r"(?:^|(?<=[.!?\n]))\s*((?:i (?:always |really )?(?:like|love|prefer|want|need|hate|dislike|don'?t like|"
                       r"don'?t want|can'?t read|use|work)|i'?m (?:a|an|not)|always |never |from now on|going forward|"
                       r"please always|please never|my (?:rule|preference) is)[^.!?\n]{4,240})", re.I)
LEARNED = "lab-learned"


def learn(text: str, where: str = "") -> list[str]:
    saved = []
    for m in STATED_RX.finditer(text or ""):
        fact = m.group(1).strip().rstrip(",;:")
        fact = fact[0].upper() + fact[1:]
        r = add_fact(LEARNED, f"{fact}" + (f" (said in {where})" if where else ""), "lab",
                     "Things Scott said in Lab sessions about how he wants things")
        if r.get("saved"):
            saved.append(fact)
    return saved


# ---- review round-trip (M3): ⬇ .md → any chatbot → ⬆ answers .md → before/after → Scott confirms -------------
REVIEW_HEAD = """# Memory review — what the AI Lab knows about Scott ({date})

**For the chatbot helping Scott:** go through this with him one subject at a time, one question at a time.
For every line ask: still true? change it? remove it? Then ask if anything is missing.
Give back the WHOLE file in the same format, changing only the tag in [ ] and the text:

- `[keep]` — still true, leave as is
- `[change] new wording` — replace the line with the new wording
- `[remove]` — drop the line
- under a subject, a new line `- ({{subject}}#new) [add] something new`

Keep every `(subject#n)` label exactly as written — the Lab matches answers by it.
Nothing changes until Scott sees a before/after and presses ✅.
"""
ANS_RX = re.compile(r"^\s*[-*]\s*\(([a-z0-9-]+)#(\d+|new)\)\s*\[(keep|change|remove|add)\]\s*(.*)$", re.I)


def review_md(names: list[str] | None = None) -> str:
    out = [REVIEW_HEAD.format(date=time.strftime("%Y-%m-%d"))]
    for s in subjects():
        if names and s["name"] not in names:
            continue
        sub = read(s["name"])
        out.append(f"\n## {sub['name']}\n_{sub['description']}_\n")
        for i, l in enumerate(sub["lines"], 1):
            out.append(f"- ({sub['name']}#{i}) [keep] {l['text']}")
    return "\n".join(out) + "\n"


def parse_answers(text: str) -> dict:
    """→ {subject: {"set": {n: new text}, "remove": {n}, "add": [text]}} + lines it could not read."""
    plan: dict[str, dict] = {}
    unread = []
    for ln in (text or "").splitlines():
        m = ANS_RX.match(ln)
        if not m:
            if re.match(r"^\s*[-*]\s*\(", ln):
                unread.append(ln.strip()[:200])
            continue
        name, n, tag, body = m.group(1).lower(), m.group(2).lower(), m.group(3).lower(), m.group(4).strip()
        p = plan.setdefault(name, {"set": {}, "remove": set(), "add": []})
        if tag == "add" and body:
            p["add"].append(body[:MAX_LINE])
        elif n != "new" and tag == "remove":
            p["remove"].add(int(n))
        elif n != "new" and tag == "change" and body:
            p["set"][int(n)] = body[:MAX_LINE]
    return {"plan": plan, "unread": unread}


def preview_answers(text: str) -> dict:
    """Before/after per subject, nothing written. Each change has an id Scott can tick."""
    parsed = parse_answers(text)
    changes, missing = [], []
    for name, p in parsed["plan"].items():
        try:
            cur = read(name)["lines"]
        except MemError:
            if p["add"]:
                for j, t in enumerate(p["add"]):
                    changes.append({"id": f"{name}+{j}", "subject": name, "kind": "add", "before": None, "after": t})
            else:
                missing.append(name)
            continue
        for n, new in sorted(p["set"].items()):
            if 1 <= n <= len(cur) and cur[n - 1]["text"] != new:
                changes.append({"id": f"{name}#{n}", "subject": name, "kind": "change", "before": cur[n - 1]["text"], "after": new})
        for n in sorted(p["remove"]):
            if 1 <= n <= len(cur):
                changes.append({"id": f"{name}#{n}", "subject": name, "kind": "remove", "before": cur[n - 1]["text"], "after": None})
        for j, t in enumerate(p["add"]):
            if t.lower() not in {l["text"].lower() for l in cur}:
                changes.append({"id": f"{name}+{j}", "subject": name, "kind": "add", "before": None, "after": t})
    return {"changes": changes, "unread": parsed["unread"], "unknown_subjects": missing}


def apply_answers(text: str, ids: list[str] | None = None) -> dict:
    """Apply the ticked changes (ids=None → all). Changed/added lines become [scott] — he confirmed them.
    One write per subject; returns how many writes so ↶ can undo the whole apply."""
    prev = preview_answers(text)
    pick = [c for c in prev["changes"] if ids is None or c["id"] in set(ids)]
    by: dict[str, list[dict]] = {}
    for c in pick:
        by.setdefault(c["subject"], []).append(c)
    writes, made = 0, []
    for name, cs in by.items():
        try:
            sub = read(name)
            lines, desc = [dict(l) for l in sub["lines"]], sub["description"]
        except MemError:
            lines, desc = [], name.replace("-", " ")
        drop = set()
        for c in cs:
            if c["kind"] in ("change", "remove"):
                n = int(c["id"].split("#")[1])
                if c["kind"] == "remove":
                    drop.add(n)
                else:
                    lines[n - 1] = {"source": "scott", "text": c["after"]}
        lines = [l for i, l in enumerate(lines, 1) if i not in drop]
        lines += [{"source": "scott", "text": c["after"]} for c in cs if c["kind"] == "add"]
        write_subject(name, desc, lines, "review", made)
        writes += 1
    return {"applied": len(pick), "writes": writes, "undo": made}


def questions(limit: int = 40) -> list[dict]:
    """🎙️ Voice review: one plain question per line, in order (Iris reads them; answers come back as a review .md)."""
    out = []
    for s in subjects():
        for i, l in enumerate(read(s["name"])["lines"], 1):
            out.append({"id": f"{s['name']}#{i}", "ask": f"About {s['name'].replace('-', ' ')}: “{l['text']}” — still true?"})
            if len(out) >= limit:
                return out
    return out

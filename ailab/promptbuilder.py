"""📝 Prompt builder (2026-11-24, M4): Scott's idea → a build prompt in his format → he edits → he sends it.

Send to (Scott picks per prompt, Lab only suggests):
  🤖 Lab agent      — small jobs; starts an agent run with the prompt as its task.
  ✳️ Claude (night) — big jobs; queues a Night Shift order for Module 0 as an AUDIT (no commits) so his permission
                      gate still holds, and gives a 📋 continue line to paste into Claude Code / Cowork.
Prompts are saved outside every repo (~/hermes-forge/lab-prompts/) — Hermes stays propose-only for the Lab.
"""
from __future__ import annotations

import importlib.util
import json
import re
import time
from pathlib import Path

from . import memory

PROMPTS_DIR = Path.home() / "hermes-forge" / "lab-prompts"
NIGHT_ORDERS = Path.home() / "hermes-forge" / "night" / "orders"
MAX_PROMPT = 60_000

TEMPLATE = """# {title} — Build Prompt ({date})

**For:** build session · **Repo:** `{repo}` · **Owner:** Scott
**Idea (Scott's words):** {idea}

---

## 0. Working rules (token-saving standard — permanent)

- **Do the work, report short.** Each module ends with ≤10 lines. Logs in `<details>`.
- **Skip what's done.** Exists and passes its check → `ALREADY DONE`, move on.
- **Flag, don't guess.** Anything unconfirmed → `UNVERIFIED:` + how to check.
- **Project standard wins:** the repo's `CLAUDE.md`. Never `git add -A`.
- **Permission gate:** after **Module 0**, STOP and ask:
  > "Would you like me to proceed with the final build based on this outline?"
- **Visuals first:** Scott can't read code yet — show the live app and plain words.

---

## 1. Locked decisions (do not re-ask)

| Area | Decision |
|---|---|
{decisions}

---

## Module 0 — Audit (read-only) → GATE

- Read what exists for this idea; list what is missing.
- Output: `docs/AUDIT_{date}_{slug}.md` + ≤10 lines in chat → **STOP at the gate.**

{modules}

## Module {last} — Live proof + handoff

- Prove it live (robot / browser / phone touch test where it is a phone UI).
- Handoff `docs/HANDOFF_{date}_{slug}.md` ending in a fenced `night` block.

---

**Continue phrase:** `continue {slug} from the {date} build prompt — Module 0`
"""

SYSTEM = """You write build prompts for Scott's software projects. Output ONLY the finished markdown prompt.
Keep EXACTLY this skeleton and these section names (fill the placeholder parts, add modules as needed):

{skeleton}

Rules: plain words (Scott can't read code yet); 3–6 small modules between Module 0 and the last one, each with
bullets and a **Check:** line a machine can test; put every choice Scott already made in "Locked decisions";
anything you are unsure of goes under a "## Gate 0 open picks" list with a default. Never invent facts about his
code — say UNVERIFIED. Keep it under 900 words."""

BIG_WORDS = re.compile(r"\b(app|studio|system|module|rebuild|redesign|migrat\w*|integrat\w*|android|windows|linux|"
                       r"database|sync|server|everything|whole|all (the )?studios|multiple|several)\b", re.I)


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")[:48] or "idea"


def size_hint(idea: str) -> dict:
    """🤖 small (Lab agent) or ✳️ big (Claude). Only a hint — Scott picks."""
    words = len((idea or "").split())
    hits = len(BIG_WORDS.findall(idea or ""))
    big = words > 60 or hits >= 2
    return {"size": "big" if big else "small",
            "why": (f"{hits} big-job words, {words} words" if big else f"looks like one small change ({words} words)")}


def latest_handoff(repo: Path | None) -> str:
    if not repo:
        return ""
    hs = sorted(list(repo.glob("docs/HANDOFF_*.md")) + list(repo.glob("HANDOFF_*.md")), key=lambda p: p.stat().st_mtime)
    if not hs:
        return ""
    t = hs[-1].read_text(errors="replace")
    return f"Latest handoff ({hs[-1].name}), first part:\n" + t[:2500]


def plain(idea: str, repo: str = "~/", title: str = "") -> str:
    """No-model draft: the skeleton with his idea dropped in. Always works, costs nothing."""
    d = time.strftime("%Y-%m-%d")
    s = slug(title or idea)
    return TEMPLATE.format(title=(title or idea.split(".")[0])[:70].strip() or "New build", date=d, repo=repo,
                           idea=idea.strip()[:1500], slug=s,
                           decisions="| What | " + idea.strip()[:200].replace("|", "/") + " |",
                           modules="## Module 1 — Build it\n\n- (fill in)\n- **Check:** (a command that proves it)\n", last=2)


def draft(lab, project: dict, provider: str, model: str, idea: str, repo_name: str = "", repo: Path | None = None) -> dict:
    """Model-written draft in his format, using his memory + the project's latest handoff."""
    idea = (idea or "").strip()
    if not idea:
        raise ValueError("Say what you want built first.")
    mem, used = memory.for_context(repo_name or project.get("name", ""), idea, budget_chars=4000)
    sk = plain("{the idea}", f"~/{repo_name}" if repo_name else "~/")
    msgs = [{"role": "system", "content": SYSTEM.replace("{skeleton}", sk) + ("\n\n" + mem if mem else "")},
            {"role": "user", "content": f"Scott's idea: {idea}\n\nProject: {repo_name or project.get('name', '')}\n\n"
                                        + latest_handoff(repo)}]
    r = lab.chat(project, provider, model, msgs, 4096, task=f"lab-prompt:{project.get('id', '')}")
    md = (r.text or "").strip()
    md = re.sub(r"^```(?:markdown|md)?\s*|\s*```$", "", md)
    if "## Module 0" not in md:                           # the model ignored the skeleton → fall back, say so
        return {"md": plain(idea, f"~/{repo_name}" if repo_name else "~/"), "usd": r.usd, "fallback": True,
                "memory_used": used, **size_hint(idea)}
    return {"md": md[:MAX_PROMPT], "usd": r.usd, "fallback": False, "memory_used": used, **size_hint(idea)}


def save(md: str, name: str = "", root: Path | None = None) -> Path:
    if "## Module 0" not in (md or ""):
        raise ValueError("A build prompt needs a Module 0 (the audit + gate).")
    d = root or PROMPTS_DIR
    d.mkdir(parents=True, exist_ok=True)
    title = re.search(r"^#\s+(.+?)(?:\s+—|\n|$)", md, re.M)
    p = d / f"BUILD_PROMPT_{time.strftime('%Y-%m-%d')}_{slug(name or (title.group(1) if title else 'idea'))}.md"
    p.write_text(md[:MAX_PROMPT])
    return p


def _hermes_validate():
    f = Path.home() / "hermes" / "forge" / "night" / "order.py"
    if not f.exists():
        return None
    try:
        spec = importlib.util.spec_from_file_location("hermes_night_order", f)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        return m.validate
    except Exception:                                    # noqa: BLE001 — fall back to our own minimal check
        return None


def night_order(prompt_path: Path, project: str, repo_path: str, slug_: str) -> dict:
    return {"project": project, "repo_path": repo_path, "risk_tier": "LOW", "module": "M0",
            "prompt_file": str(prompt_path), "prompt_anchor": "## Module 0",
            "acceptance": [{"kind": "review", "check": "night_out/AUDIT.md lists what exists, what is missing, and the gate question"}],
            "budget_usd": 2.0, "max_turns": 40, "priority": 5, "status": "queued", "kind": "audit",
            "slug": f"{slug_ if slug_.startswith('lab-') else 'lab-' + slug_}-m0", "source_handoff": str(prompt_path)}


def queue_for_claude(prompt_path: Path, project: str, repo_path: str, orders: Path | None = None) -> dict:
    """Queue Module 0 as a night AUDIT order (no commits) + the continue line for a live session."""
    s = slug(prompt_path.stem.split("_", 3)[-1])
    o = night_order(prompt_path, project, repo_path, s)
    v = _hermes_validate()
    errs = v(o) if v else [k for k in ("project", "repo_path", "prompt_file") if not o.get(k)]
    out = {"continue": f"continue {s} from {prompt_path} — Module 0", "order": None, "refused": errs}
    if errs:
        return out
    d = orders or NIGHT_ORDERS
    d.mkdir(parents=True, exist_ok=True)
    f = d / f"{re.sub(r'[^a-z0-9]+', '-', project.lower())}__{o['slug']}.json"
    if f.exists():
        out["refused"] = [f"an order called {f.name} is already queued"]
        return out
    f.write_text(json.dumps(o, indent=2) + "\n")
    out["order"] = str(f)
    return out


def listing(root: Path | None = None) -> list[dict]:
    d = root or PROMPTS_DIR
    return [{"file": str(p), "name": p.name, "at": p.stat().st_mtime}
            for p in sorted(d.glob("BUILD_PROMPT_*.md"), key=lambda p: -p.stat().st_mtime)[:50]] if d.exists() else []

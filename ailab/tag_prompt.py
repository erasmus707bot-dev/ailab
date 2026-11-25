"""🏷 Tag prompts for the anime models — Lab side (thin client since eyes+story+rip follow-up 5, 2026-11-25).

Illustrious XL and Pony V6 read Danbooru comma tags, not sentences (M3 proof 2026-11-24: Illustrious got "a girl with
a red umbrella at a rainy bus stop" and drew a closed umbrella, no rain, a park bench).
Which model reads what — and the tag writer's instructions, the clean-up, the no-writer rules and the final build — now
live in Hermes: forge/studios/comfy/prompt_dialect.py, tool `prompt_style` (models.py `dialect`). One place for every
studio. The Lab keeps only the writer loop, because the writer call is the Lab's own (its key, spend and cap).
The prompt is: <tags>, <Scott's words exactly as typed>. Hermes adds the quality tags + negative on the card.
Hermes away or too old → the model is treated as a sentence model (his words go as they are), never a guess.
"""
from __future__ import annotations

import time

from .mcp_client import HermesRefused

TTL_S = 600
_STYLE: dict[str, tuple[float, dict]] = {}


def forget() -> None:
    _STYLE.clear()


def style(run, model: str) -> dict:
    """Hermes prompt_style for `model` (cached 10 min). Any failure → sentence."""
    hit = _STYLE.get(model)
    if hit and time.time() - hit[0] < TTL_S:
        return hit[1]
    try:
        s = run.lab.mcp.call("prompt_style", {"model": model}) or {}
    except (HermesRefused, OSError, ValueError, AttributeError):
        s = {}
    s = s if s.get("dialect") in ("tags", "sentence") else {"dialect": "sentence"}
    _STYLE[model] = (time.time(), s)
    return s


def wants(model: str, run=None) -> bool:
    """True when the model reads comma tags (asks Hermes; cached)."""
    if not model:
        return False
    if run is None:
        hit = _STYLE.get(model)
        return bool(hit and hit[1].get("dialect") == "tags")
    return style(run, model).get("dialect") == "tags"


def _shape(run, model: str, mine: str, look_words: list[str], add: str, reply: str | None) -> dict:
    a = {"model": model, "mine": mine, "look": look_words[:20], "add": add}
    if reply is not None:
        a["reply"] = reply
    return run.lab.mcp.call("prompt_style", a) or {}


def write(run, writer_list, model: str, mine: str, look_words: list[str], add: str = "", stage=None) -> tuple[list[str], str, str]:
    """(tags, who made them, final prompt). Writers in order with Hermes's instructions; Hermes cleans each reply.
    A refusal, junk or an error moves on; Hermes's simple rules when no writer helps."""
    s = style(run, model)
    system = s.get("system") or ""
    ask = mine + (f"\nLook: {', '.join(look_words)}" if look_words else "") + (f"\nDetail: {add}" if add else "")
    for prov, wmodel in writer_list if system else []:
        try:
            if stage:
                stage(run, "🏷", f"Turning your words into tags with {wmodel.split('/')[-1]}")
            r = run.lab.chat(run.project, prov, wmodel,
                             [{"role": "system", "content": system}, {"role": "user", "content": ask}], 200,
                             cap_usd=max(0.0, run.cap_usd - run.usd), task=f"lab-picture:{run.project['id']}")
            run.usd += float(r.usd or 0)
            run.tokens_in += int(getattr(r, "tokens_in", 0) or 0)
            run.tokens_out += int(getattr(r, "tokens_out", 0) or 0)
            got = _shape(run, model, mine, look_words, add, (r.text or "").strip())
            if got.get("by") == "writer" and got.get("tags"):
                return list(got["tags"]), f"{prov}/{wmodel}", str(got.get("prompt") or "")
        except Exception:                                        # noqa: BLE001 — try the next writer
            continue
    try:
        got = _shape(run, model, mine, look_words, add, None)
        return list(got.get("tags") or []), "rules", str(got.get("prompt") or mine)
    except Exception:                                            # noqa: BLE001 — Hermes away: his words as they are
        return [], "rules", mine

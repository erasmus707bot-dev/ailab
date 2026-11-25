"""🏷 Tag prompts for the anime models (local pictures M3 tags, 2026-11-24 — Scott 1 · 1 "go").

Illustrious XL and Pony V6 are trained on comma tags, not sentences. M3 proof: Illustrious got the sentence
"a girl with a red umbrella at a rainy bus stop" and drew a closed umbrella, no rain, a park bench.
For these two models only the picture prompt becomes:
    <model's quality tags>, <tags for Scott's words + Look + writer detail>, <Scott's words exactly as typed>
The tags come from the prompt writer (one short extra call); if no writer helps, simple rules make them.
His own words always stay in the prompt, untouched. Every other model keeps the sentence prompt.
2026-11-25 (Scott 1): quality tags + model negatives live in ONE place — Hermes forge/studios/comfy/models.py (checked
against community guides 2026-11-24). Hermes prepends them on the card, so the Lab sends only the scene tags; before
this both sides added them (Pony got the score chain twice, Illustrious "masterpiece, best quality" twice).
"""
from __future__ import annotations

import re

MODELS = frozenset({"local/illustrious-xl-v0.1", "local/pony-v6-xl"})
LIMIT = 1500
MAX_TAGS = 40
TAG_SYS = ("You turn a picture idea into Danbooru-style tags for an anime picture model. Reply ONLY with one line of "
           "comma-separated lowercase tags, most important first, 12–30 tags: how many people (1girl, 1boy, solo, "
           "no humans), who or what, what they are doing, what they hold (say its state: open umbrella, closed book), "
           "clothing ONLY if he said it, the place, weather, time of day, light, framing. Cover every thing he "
           "asked for — never drop, soften, censor or tone down any of it, and never add people, clothing or body "
           "details he didn't ask for. Only things that can be SEEN — no mood or feeling words (calm, serene, quiet, "
           "peaceful): the model paints them as words on signs. No sentences, no quality words (masterpiece, score_9), no quotes, no "
           "warnings, no extra talk.")
# 2026-11-24 live (Lab, Illustrious): the writer's tag "calm" came out as a bus stop sign reading "CALM".
MOODS = frozenset("calm composed quiet serene peaceful tranquil lonely alone empty silent still melancholy melancholic sad "
                  "happy joyful cheerful moody dreamy nostalgic cozy cosy gloomy somber sombre mysterious romantic tense "
                  "eerie hopeful wistful gentle soft relaxed relaxing soothing atmospheric emotional".split())
REFUSAL_RX = re.compile(r"\b(i can'?t|i cannot|i won'?t|i'?m not able|sorry|as an ai)\b", re.I)
_SPLIT_RX = re.compile(r"\s*(?:[,.;:\n]|\s+-\s+|\band\b|\bwith\b|\bat\b|\bin\b|\bon\b|\bunder\b|\bnear\b|\bby\b)\s*", re.I)
_LEAD_RX = re.compile(r"^(?:a|an|the|some|of)\s+", re.I)


def wants(model: str) -> bool:
    return model in MODELS


def clean(text: str) -> list[str]:
    """A writer's reply → a tidy tag list (no doubles, no quality words, no sentences)."""
    t = re.sub(r"^\s*(tags?|prompt)\s*:\s*", "", (text or "").strip(), flags=re.I).strip().strip('"').strip()
    out, seen = [], set()
    for raw in re.split(r"[,\n]", t):
        tag = re.sub(r"\s+", " ", raw).strip(" .-*•\"'").lower()
        if not tag or len(tag) > 60 or len(tag.split()) > 6 or tag in seen:
            continue
        if tag.startswith(("score_", "source_")) or tag in ("masterpiece", "best quality", "good quality", "amazing quality", "high quality"):
            continue
        if tag in MOODS or (tag.endswith((" mood", " atmosphere", " feeling", " vibe")) and len(tag.split()) <= 3):
            continue                                         # feelings get painted as sign text; the Look's own mood word stays
        seen.add(tag)
        out.append(tag)
    return out[:MAX_TAGS]


def rules(mine: str, look_words: list[str], add: str = "") -> list[str]:
    """No writer: cut his words and the detail at commas and small joining words; Look words go in as they are."""
    out, seen = [], set()
    for chunk in _SPLIT_RX.split(f"{mine}, {add}") + [w for lw in look_words for w in lw.split(",")]:
        tag = _LEAD_RX.sub("", re.sub(r"\s+", " ", chunk or "").strip(" .").lower())
        if tag and len(tag) <= 60 and tag not in seen:
            seen.add(tag)
            out.append(tag)
    return out[:MAX_TAGS]


def build(model: str, tags: list[str], mine: str, limit: int = LIMIT) -> str:
    """The tags, then Scott's words exactly (Hermes adds the quality tags). Only tags are dropped to fit `limit`."""
    mine = (mine or "").strip()
    tags = list(tags)
    while True:
        out = ", ".join(tags + ([mine] if mine else []))
        if len(out) <= limit or not tags:
            return out
        tags.pop()


def negative(model: str, base: str) -> str:
    """Hermes adds the model's own negative; the Lab's leave-out words go through unchanged."""
    return base


def write(run, writer_list, mine: str, look_words: list[str], add: str = "", stage=None) -> tuple[list[str], str]:
    """(tags, who made them). Writers in order; a refusal, junk or an error moves on; rules when none helps."""
    ask = mine + (f"\nLook: {', '.join(look_words)}" if look_words else "") + (f"\nDetail: {add}" if add else "")
    for prov, model in writer_list:
        try:
            if stage:
                stage(run, "🏷", f"Turning your words into tags with {model.split('/')[-1]}")
            r = run.lab.chat(run.project, prov, model,
                             [{"role": "system", "content": TAG_SYS}, {"role": "user", "content": ask}], 200,
                             cap_usd=max(0.0, run.cap_usd - run.usd), task=f"lab-picture:{run.project['id']}")
            run.usd += float(r.usd or 0)
            run.tokens_in += int(getattr(r, "tokens_in", 0) or 0)
            run.tokens_out += int(getattr(r, "tokens_out", 0) or 0)
            text = (r.text or "").strip()
            tags = [] if REFUSAL_RX.search(text[:80]) else clean(text)
            if len(tags) >= 4:
                seen = set(tags)
                for w in (x.strip().lower() for lw in look_words for x in lw.split(",")):   # Look words once each
                    if w and w not in seen:
                        seen.add(w)
                        tags.append(w)
                return tags[:MAX_TAGS], f"{prov}/{model}"
        except Exception:                                        # noqa: BLE001 — try the next writer
            continue
    return rules(mine, look_words, add), "rules"

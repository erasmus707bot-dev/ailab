#!/usr/bin/env python3
"""🏁 R4 rung 1 — the arm-wrestle rebuild test, end to end, one command (build prompt #2, Scott 2026-11-25:
"you do it with the arm wrestling clip. make them two women instead of men as the test").

    python3 ~/ailab/tools/r4_rung1.py            # $0 path: local pictures, 🆓 pan-and-zoom, narrator if Kokoro is on

Talks to the AI Lab on 127.0.0.1:8850 (gandalf only). Steps: 🎞 break the clip down (Hermes, $0) → 🎭 design a cast of
2 women (Lab, local pictures) → 🎬 rebuild at level 2 with them → read ⚖️ the review record → write a report.
Questions the Lab asks are answered with its ⭐ pick — EXCEPT any price card: the script always picks the $0 choice,
so it never spends. Report: ~/hermes-data/ailab/video-testing/R4_RUNG1_<time>.md (+ .json). Safe to re-run: a finished
breakdown and cast are reused (--new-cast designs a fresh cast; --fresh re-reads the clip and starts a new rebuild).
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request
from pathlib import Path

LAB = "http://127.0.0.1:8850"
PROJECT = "video-testing"
CLIP = "videos/rebuild-test-R7oUAWXxP60.mp4"
PASS_SCORE = 70
OUT = Path.home() / "hermes-data" / "ailab" / PROJECT


def call(path: str, body: dict | None = None, timeout: int = 60) -> dict:
    req = urllib.request.Request(LAB + path, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json", "Sec-Fetch-Site": "same-origin"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read() or b"{}")


def say(msg: str) -> None:
    print(time.strftime("%H:%M:%S"), msg, flush=True)


def free_pick(q: dict) -> str:
    """⭐ pick, but never a paid choice: anything with a $ price that isn't $0 is skipped."""
    import re
    ch = q.get("choices") or []
    free = [c for c in ch if not re.search(r"\$\s*(?!0(?:\.0+)?\b)\d", c)]
    items = q.get("items") or []
    if len(items) > 1:                                           # a multi-question card: answer each with its ⭐ (free) pick
        parts = []
        for it in items:
            cs = it.get("choices") or []
            fs = [c for c in cs if not re.search(r"\$\s*(?!0(?:\.0+)?\b)\d", c)] or cs
            best = cs[it.get("best", 0)] if cs and cs[it.get("best", 0)] in fs else fs[0]
            parts.append(f"{it.get('q', '')} → {best}")
        return " · ".join(parts)
    best = ch[q.get("best", 0)] if ch and q.get("best", 0) < len(ch) else (ch[0] if ch else "")
    return best if best in free else (free[0] if free else best)


def run_until_done(rid: str, label: str, limit_s: int = 3 * 3600) -> dict:
    t0, last, answered, answered_at = time.time(), "", set(), {}
    while time.time() - t0 < limit_s:
        try:
            v = call(f"/api/agent/run?id={rid}")["run"]
        except Exception as e:                                   # noqa: BLE001 — Lab restarting: wait, don't crash
            say(f"{label}: Lab not answering ({e}) — waiting")
            time.sleep(15)
            continue
        q = v.get("question")
        key = json.dumps(q, sort_keys=True) if q else ""
        if q and key not in answered and v["state"] not in ("done", "failed", "stopped"):
            ans = free_pick(q)
            say(f"❓ {q.get('text', '')[:120]} → {ans[:160]}")
            try:
                call("/api/agent/answer", {"id": rid, "answer": ans})
                answered.add(key)
                answered_at[key] = time.time()
            except Exception as e:                               # noqa: BLE001 — asked again next loop
                say(f"❓ answer not taken yet: {e}")
        if v["state"] in ("done", "failed", "stopped"):
            return v
        if v["state"] == "interrupted":                          # live rung 2 2026-11-25: a Lab restart at 17:10 left the run
            say(f"{label}: 🔄 the Lab restarted — resuming (finished shots are kept)")   # waiting for ▶ Resume for an hour
            try:
                call("/api/agent/resume", {"id": rid})
            except Exception as e:                               # noqa: BLE001 — Lab still starting; next loop tries again
                say(f"🔄 resume not taken yet: {e}")
        if q and key in answered and time.time() - answered_at.get(key, 0) > 60:
            answered.discard(key)                                # same card again (or answer lost) → answer it again
        stage = ((v.get("steps") or [{}])[-1].get("why") or "")[:110]
        if stage != last:
            say(f"{label}: {stage}")
            last = stage
        time.sleep(10)
    raise SystemExit(f"⏱ {label} took more than {limit_s // 60} minutes — stopped waiting (it keeps running in the Lab).")


def main(argv: list[str]) -> int:
    new_cast = "--new-cast" in argv
    fresh = "--fresh" in argv                                    # new breakdown recipes + a new rebuild record
    # 1 · breakdown
    say("🎞 breaking the clip down (Hermes, $0)…")
    r = call("/api/breakdown/start", {"project": PROJECT, "path": CLIP, "fresh": fresh})
    if not r.get("ok"):
        raise SystemExit(f"🎞 {r.get('message')}")
    bid = r["id"]
    while r.get("state") == "running":
        time.sleep(8)
        s = call(f"/api/breakdown/status?key={r['key']}")
        if s.get("state") != "running":
            if s.get("state") != "done":
                raise SystemExit(f"🎞 breakdown stopped: {(s.get('error') or {}).get('message')} — run this again, finished scenes are kept.")
            break
        say(f"🎞 {(s.get('detail') or {}).get('phase')}")
    bd = call(f"/api/breakdown?id={bid}")
    say(f"🎞 {bd.get('count')} scenes · transcript: {bd.get('transcript') or 'none'}")
    # 2 · cast of two women
    have = call(f"/api/cast?project={PROJECT}")
    if new_cast or not (have.get("chosen") or {}).get("ids"):
        say("🎭 designing a cast of 2 women…")
        st = call("/api/agent/start", {"project": PROJECT, "task": "Design a cast of 2 women for an arm-wrestling match",
                                       "ctypes": ["image"], "batch": {"cast": {"n": 2, "who": "woman"}}})
        if not st.get("ok"):
            raise SystemExit(f"🎭 {st.get('message')}")
        v = run_until_done(st["run"]["id"], "🎭 cast")
        say(f"🎭 {v['state']}: {v.get('why', '')[:300]}")
        if v["state"] != "done":
            return 1
    else:
        say(f"🎭 reusing this project's cast: {have['chosen']['cast']} (--new-cast to design another)")
    # 3 · rebuild, level 2, free clips
    say("🎬 rebuilding at level 2 (same shots), 🆓 pan-and-zoom…")
    st = call("/api/agent/start", {"project": PROJECT, "task": "Rebuild the arm-wrestle clip with my cast", "ctypes": ["image"],
                                   "batch": {"rebuild": {"bd": bid, "level": 2, "clips": "free", "audio": "narrate", "voice": "narrator", "fresh": fresh}}})
    if not st.get("ok"):
        raise SystemExit(f"🎬 {st.get('message')}")
    v = run_until_done(st["run"]["id"], "🎬 rebuild")
    say(f"🎬 {v['state']}: {v.get('why', '')[:400]}")
    # 4 · report
    rec = call(f"/api/rebuild?project={PROJECT}&bd={bid}")
    beats = rec.get("beats") or []
    rows, fails = [], 0
    for b in beats:
        sc = (b.get("eyes") or {}).get("score")
        ids = (b.get("identity") or []) + (b.get("clip_identity") or [])
        ok = sc is not None and sc >= PASS_SCORE and not ids and b.get("still")
        fails += not ok
        rows.append(f"| {b['k'] + 1} | {b['scene'] + 1} | {b['start']:.1f}–{b['end']:.1f} s | {sc if sc is not None else '—'} | "
                    f"{', '.join(ids) or '—'} | {'✅' if ok else '❌'} {b.get('error') or ''} |")
    spend = sum(float(b.get("usd") or 0) for b in beats)
    verdict = "✅ PASS" if beats and not fails else "❌ NOT YET"
    md = [f"# R4 rung 1 — arm-wrestle rebuild with 2 women — {verdict}", "",
          f"- Clip: `{CLIP}` (project {PROJECT}) · breakdown `{bid}` · {len(beats)} shots · spend ${spend:.3f}",
          f"- Cast: {', '.join((rec.get('settings') or {}).get('cast') or [])} · film: `{rec.get('film') or '—'}`",
          f"- Pass bar: every shot 👁 ≥ {PASS_SCORE} % with no identity miss · failed shots: {fails}",
          *[f"- Note: {n}" for n in rec.get("notes") or []], "",
          "| shot | scene | time | 👁 score | identity misses | |", "|---|---|---|---|---|---|", *rows, "",
          "Open the Lab → video-testing → 🎬 Rebuild a video with my cast → ⚖️ Review to watch it side by side and 🔁 retry a shot."]
    stamp = time.strftime("%Y%m%d-%H%M")
    (OUT / f"R4_RUNG1_{stamp}.md").write_text("\n".join(md) + "\n")
    (OUT / f"R4_RUNG1_{stamp}.json").write_text(json.dumps({"breakdown": bd, "rebuild": rec}, indent=1, default=str))
    say(f"{verdict} — report: {OUT / f'R4_RUNG1_{stamp}.md'}")
    return 0 if verdict.startswith("✅") else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

#!/usr/bin/env python3
"""🏁 R4 rung 2 — the Twister final exam (build prompt #2 R4: "a Twister clip, same cast. Report per-shot failures
plainly (merged limbs / swaps)").

    python3 ~/ailab/tools/r4_rung2.py            # clip A only ($0: local pictures, 🆓 pan-and-zoom, narrator)
    python3 ~/ailab/tools/r4_rung2.py --all      # clips A, B, C in a row (~3x the GPU time)
    python3 ~/ailab/tools/r4_rung2.py B          # one named clip
    python3 ~/ailab/tools/r4_rung2.py --retry-failed [A|--all]   # 🔁 each failed shot once ($0), then a new report

Same flow and $0 rules as r4_rung1.py (its helpers are reused): 🎞 breakdown (a finished one is reused — clip A's
`bd-fa40e7996c89a744` already exists) → the project's cast (Mara + Dina, never redesigned here) → 🎬 rebuild level 2 →
report. Each failed shot is named plainly: merged limbs · swap · onlooker copy · wrong head-count · lost look · low score.
Report: ~/hermes-data/ailab/video-testing/R4_RUNG2_<time>.md (+ .json). A failed rung is a finding, not a bug hunt.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from r4_rung1 import OUT, PASS_SCORE, PROJECT, call, run_until_done, say  # noqa: E402

CLIPS = {"A": "videos/twister-rung2-A-t1.mp4", "B": "videos/twister-rung2-B-t1.mp4", "C": "videos/twister-rung2-C-t1.mp4"}


def kind_of(miss: str) -> str:
    m = miss.lower()
    if "merged limbs" in m:
        return "merged limbs"
    if m.startswith("no swap"):
        return "swap"
    if m.startswith("anyone else"):
        return "onlooker copy"
    if m.startswith("exactly "):
        return "wrong head-count"
    return "lost look"                                            # a cast member's own hair + outfit not found


def shot_fails(b: dict) -> list[str]:
    sc = (b.get("eyes") or {}).get("score")
    kinds = sorted({kind_of(m) for m in (b.get("identity") or []) + (b.get("clip_identity") or [])})
    if sc is not None and sc < PASS_SCORE:
        kinds.append("low score")
    if not b.get("still"):
        kinds.append("no picture")
    if sc is None and not kinds:
        kinds.append("no 👁 score")
    return kinds


def retry_failed(name: str, clip: str) -> None:
    r = call("/api/breakdown/start", {"project": PROJECT, "path": clip, "fresh": False})
    if not r.get("ok") or r.get("state") == "running":
        say(f"🔁 {name}: no finished breakdown — run without --retry-failed first")
        return
    bid = r["id"]
    beats = call(f"/api/rebuild?project={PROJECT}&bd={bid}").get("beats") or []
    todo = [b["k"] for b in beats if shot_fails(b)]
    say(f"🔁 {name}: retrying shots {', '.join(str(k + 1) for k in todo) or 'none'} ($0)")
    for k in todo:
        st = call("/api/agent/start", {"project": PROJECT, "task": f"Retry Twister clip {name} shot {k + 1}", "ctypes": ["image"],
                                       "batch": {"rebuild": {"bd": bid, "level": 2, "clips": "free", "audio": "narrate",
                                                             "voice": "narrator", "retry": k}}})
        if not st.get("ok"):
            say(f"🔁 shot {k + 1}: {st.get('message')}")
            continue
        v = run_until_done(st["run"]["id"], f"🔁 {name} shot {k + 1}")
        say(f"🔁 {name} shot {k + 1} {v['state']}: {v.get('why', '')[:200]}")


def one_clip(name: str, clip: str, fresh: bool) -> dict:
    say(f"🎞 clip {name}: breaking it down (Hermes, $0, reused if done)…")
    r = call("/api/breakdown/start", {"project": PROJECT, "path": clip, "fresh": fresh})
    if not r.get("ok"):
        return {"name": name, "clip": clip, "error": f"🎞 {r.get('message')}"}
    bid = r["id"]
    while r.get("state") == "running":
        time.sleep(8)
        s = call(f"/api/breakdown/status?key={r['key']}")
        if s.get("state") != "running":
            if s.get("state") != "done":
                return {"name": name, "clip": clip, "bd": bid,
                        "error": f"🎞 breakdown stopped: {(s.get('error') or {}).get('message')} — run again, finished scenes are kept."}
            break
        say(f"🎞 {(s.get('detail') or {}).get('phase')}")
    bd = call(f"/api/breakdown?id={bid}")
    say(f"🎞 {bd.get('count')} scenes")
    say(f"🎬 clip {name}: rebuilding at level 2, 🆓 pan-and-zoom…")
    st = call("/api/agent/start", {"project": PROJECT, "task": f"Rebuild the Twister clip {name} with my cast", "ctypes": ["image"],
                                   "batch": {"rebuild": {"bd": bid, "level": 2, "clips": "free", "audio": "narrate",
                                                         "voice": "narrator", "fresh": fresh}}})
    if not st.get("ok"):
        return {"name": name, "clip": clip, "bd": bid, "error": f"🎬 {st.get('message')}"}
    v = run_until_done(st["run"]["id"], f"🎬 {name}")
    say(f"🎬 {name} {v['state']}: {v.get('why', '')[:300]}")
    return {"name": name, "clip": clip, "bd": bid, "breakdown": bd, "rebuild": call(f"/api/rebuild?project={PROJECT}&bd={bid}")}


def section(res: dict) -> tuple[list[str], int, float, dict]:
    if res.get("error"):
        return [f"## Clip {res['name']} — ❌ did not run", "", f"- `{res['clip']}` · {res['error']}", ""], 1, 0.0, {}
    rec = res["rebuild"]
    beats = rec.get("beats") or []
    rows, fails, tally = [], 0, {}
    for b in beats:
        sc = (b.get("eyes") or {}).get("score")
        misses = (b.get("identity") or []) + (b.get("clip_identity") or [])
        kinds = shot_fails(b)
        ok = not kinds
        fails += not ok
        for k in kinds:
            tally[k] = tally.get(k, 0) + 1
        rows.append(f"| {b['k'] + 1} | {b['start']:.1f}–{b['end']:.1f} s | {sc if sc is not None else '—'} | "
                    f"{'✅' if ok else '❌ ' + ', '.join(kinds)} | {'; '.join(misses) or '—'} {b.get('error') or ''} |")
    spend = sum(float(b.get("usd") or 0) for b in beats)
    head = "✅ PASS" if beats and not fails else "❌ NOT YET"
    md = [f"## Clip {res['name']} — {head}", "",
          f"- `{res['clip']}` · breakdown `{res['bd']}` · {len(beats)} shots · spend ${spend:.3f} · film `{rec.get('film') or '—'}`",
          f"- Failed shots: {fails} · by kind: {', '.join(f'{k} {n}' for k, n in sorted(tally.items())) or 'none'}",
          *[f"- Note: {n}" for n in rec.get("notes") or []], "",
          "| shot | time | 👁 | result | what 👁 flagged |", "|---|---|---|---|---|", *rows, ""]
    return md, fails + (0 if beats else 1), spend, tally


def main(argv: list[str]) -> int:
    fresh = "--fresh" in argv
    names = ["A", "B", "C"] if "--all" in argv else [a.upper() for a in argv if a.upper() in CLIPS] or ["A"]
    cast = call(f"/api/cast?project={PROJECT}").get("chosen") or {}
    if not cast.get("ids"):
        raise SystemExit("🎭 no cast chosen in video-testing — run r4_rung1.py first (rung 2 must use the same cast).")
    say(f"🎭 same cast as rung 1: {cast.get('cast')}")
    if "--retry-failed" in argv:
        for n in names:
            retry_failed(n, CLIPS[n])
    results = [one_clip(n, CLIPS[n], fresh) for n in names]
    body, fails, spend, tally = [], 0, 0.0, {}
    for res in results:
        md, f, s, t = section(res)
        body += md
        fails, spend = fails + f, spend + s
        for k, n in t.items():
            tally[k] = tally.get(k, 0) + n
    verdict = "✅ PASS" if not fails else "❌ NOT YET"
    md = [f"# R4 rung 2 — Twister rebuild with {cast.get('cast')} — {verdict}", "",
          f"- Clips: {', '.join(names)} · level 2 · spend ${spend:.3f} · pass bar: every shot 👁 ≥ {PASS_SCORE} % and no identity miss",
          f"- Failures by kind: {', '.join(f'{k} {n}' for k, n in sorted(tally.items())) or 'none'}",
          "- Kinds: merged limbs = bodies fused · swap = one woman's hair with the other's clothes · onlooker copy = a bystander "
          "wears a cast look · wrong head-count · lost look = a cast member's hair/outfit missing · low score = recipe miss", "",
          *body, "Open the Lab → video-testing → 🎬 Rebuild → ⚖️ Review to watch side by side and 🔁 retry a shot ($0)."]
    stamp = time.strftime("%Y%m%d-%H%M")
    (OUT / f"R4_RUNG2_{stamp}.md").write_text("\n".join(md) + "\n")
    (OUT / f"R4_RUNG2_{stamp}.json").write_text(json.dumps(results, indent=1, default=str))
    say(f"{verdict} — report: {OUT / f'R4_RUNG2_{stamp}.md'}")
    return 0 if not fails else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

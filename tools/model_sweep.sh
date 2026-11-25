#!/usr/bin/env bash
# 🧪 Model sweep (2026-11-24, Scott: "test that prompt against all other models that might be capable of uncensored art …
# so things work smoother and less trial and error later"). One idea → every 🔓 writer (≈$0.01 all) → every Venice
# video model built for uncensored output (quoted first, cheapest first, stops at the budget).
# Run on gandalf:   bash ~/ailab/tools/model_sweep.sh                 # words = newest idea in video-testing
#                   bash ~/ailab/tools/model_sweep.sh "my words"      # your own words
# Env: BUDGET=3.00 (video $ limit for this sweep) · SECS=5 · ALSO="id1 id2" (extra video model ids, e.g. normal Wan 3.0)
#      WRITERS_ONLY=1 · VIDEO_ONLY=1 · PROJECT=video-testing · ONLY="id1 id2" (just these video models)
# Out: ~/hermes-data/ailab/<project>/sweeps/<stamp>/  (clips, results.json) + docs/SWEEP_<stamp>.md (scorecard)
set -u
cd "$HOME/hermes" || exit 1
PYTHONPATH="$HOME/hermes:$HOME/ailab" python3 - "${1:-}" <<'PY'
import base64, json, os, re, shutil, sys, time, urllib.request
from pathlib import Path
from forge.projects import mcp_server as M
from ailab import picture, roster, video

PROJECT = os.environ.get("PROJECT", "video-testing")
ROOT = Path.home() / "hermes-data/ailab" / PROJECT
BUDGET, SECS = float(os.environ.get("BUDGET", "3.00")), int(os.environ.get("SECS", "5"))
ALSO = os.environ.get("ALSO", "").split()
STAMP = time.strftime("%Y%m%d-%H%M%S")
OUT = ROOT / "sweeps" / STAMP
OUT.mkdir(parents=True, exist_ok=True)
ctx = M.ctx_for("builder", "ailab", category="ailab")
SOFT_RX = re.compile(r"\b(tasteful\w*|implied|suggest(?:ed|ive)ly|modest\w*|cover(?:ed|ing)|draped?|clothed|dressed|wearing|"
                     r"robe|towel|sheer fabric|strategic\w*|silhouette|censor\w*|blur\w*|pg-?13|safe for work)\b", re.I)
UNC_VIDEO_RX = re.compile(r"enhanced|chili|spicy|uncensored")


def call(n, a):
    r = M.call_tool(n, a, ctx)
    sc = r.get("structuredContent") or {}
    if r.get("isError"):
        raise RuntimeError(f"{sc.get('code')}: {sc.get('message')}" + (f" | {sc.get('fix')}" if sc.get("fix") else ""))
    return sc


def idea() -> str:
    if len(sys.argv) > 1 and sys.argv[1].strip():
        return sys.argv[1].strip()
    for f in sorted((ROOT / "docs").glob("HANDOFF_*.md"), key=lambda p: p.stat().st_mtime, reverse=True):
        m = re.search(r"^\*\*Idea:\*\*\s*(.+)$", f.read_text(errors="replace"), re.M)
        if m:
            return m.group(1).strip()
    sys.exit("No words given and no **Idea:** line found — run: bash ~/ailab/tools/model_sweep.sh \"your words\"")


WORDS = idea()
MINE = picture.own_words(WORDS)
print(f"== 🧪 sweep {STAMP} · project {PROJECT}\n== words: {WORDS}\n")

# ---------- 1. writers ----------
def uncensored_writers():
    rows = []
    for r in getattr(roster, "ROSTER", None) or getattr(roster, "ROWS", None) or []:
        if roster.limits_tag(r["provider"], r["id"]) == roster.UNCENSORED:
            rows.append((r["provider"], r["id"]))
    return rows


def ollama(model, msgs):
    req = urllib.request.Request("http://127.0.0.1:11434/api/chat", json.dumps(
        {"model": model, "messages": msgs, "stream": False, "options": {"num_predict": 300}}).encode(),
        {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as r:
        return (json.loads(r.read()).get("message") or {}).get("content") or ""


def clean_add(text):
    add = re.sub(r"^\s*(prompt|details?)\s*:\s*", "", (text or "").strip(), flags=re.I).strip().strip('"').strip()
    if add.lower().startswith(MINE.lower()):
        add = add[len(MINE):].lstrip(" ,.;:-").strip()
    return add


writers = []
if not os.environ.get("VIDEO_ONLY"):
    msgs = [{"role": "system", "content": video.MOTION_SYS}, {"role": "user", "content": f"{WORDS}\nLength: {SECS} s\nShape: 9:16"}]
    print("== 1. writers (motion detail after your words)")
    for prov, mid in uncensored_writers():
        row = {"provider": prov, "model": mid, "verdict": "", "usd": 0.0, "ms": 0, "words": 0, "text": "", "note": ""}
        t0 = time.time()
        try:
            if prov == "ollama":
                text = ollama(mid, msgs)
            else:
                r = call("llm_call", {"provider": prov, "model": mid, "messages": msgs, "max_tokens": 300, "task": "model-sweep"})
                text, row["usd"] = r.get("text") or "", float(r.get("usd") or 0)
                if not text.strip():                               # thinking models can spend all 300 tokens thinking
                    r = call("llm_call", {"provider": prov, "model": mid, "messages": msgs, "max_tokens": 1500, "task": "model-sweep"})
                    text, row["usd"] = r.get("text") or "", row["usd"] + float(r.get("usd") or 0)
                    row["note"] = "empty at 300 tokens — needed 1500 (thinking model: slow + dearer as a writer)"
            add = clean_add(text)
            row.update(ms=int((time.time() - t0) * 1000), text=add, words=len(add.split()))
            soft = sorted({m.group(0).lower() for m in SOFT_RX.finditer(add)})
            if len(add) < 5:
                row["verdict"], row["note"] = "⚠️ empty", "wrote nothing even with 1500 tokens — not a refusal message"
            elif picture.REFUSAL_RX.search(add[:160]):
                row["verdict"] = "❌ refused"
            elif soft:
                row["verdict"], row["note"] = "⚠️ may soften", "says: " + ", ".join(soft)
            elif row["words"] > 70:
                row["verdict"], row["note"] = "⚠️ too long", f"{row['words']} words (asked 15–45)"
            else:
                row["verdict"] = "✅ ok" if not row["note"] else "⚠️ slow thinker"
        except Exception as e:                                     # noqa: BLE001 — report and carry on
            row.update(ms=int((time.time() - t0) * 1000), verdict="💥 error", note=str(e)[:160])
            if prov == "ollama" and "404" in str(e):
                row.update(verdict="⏭ not installed", note=f"not on this computer — `ollama pull {mid}` to test it")
        writers.append(row)
        print(f"  {row['verdict']:<14} {prov}/{mid}  {row['ms']} ms ${row['usd']:.4f} {row['note']}")
    (OUT / "results.json").write_text(json.dumps({"words": WORDS, "writers": writers}, indent=1))

# ---------- 2. video models ----------
videos = []
if not os.environ.get("WRITERS_ONLY"):
    good = next((w for w in writers if w["verdict"] == "✅ ok" and "abliterat" in w["model"]), None) or \
           next((w for w in writers if w["verdict"] == "✅ ok"), None)
    add = good["text"] if good else ""
    prompt = (f"{MINE.rstrip('.')}. {add}" if add else MINE)[:2500]
    print(f"\n== 2. video models · same prompt for all (motion from {good['model'] if good else 'nobody — your words only'})")
    pic = max((p for p in (ROOT / "pictures").glob("*") if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp")
               and p.stat().st_size <= 12_000_000), key=lambda p: p.stat().st_mtime, default=None)
    print(f"   first frame for picture→video: {pic.name if pic else 'NONE — picture→video models skipped'}")
    try:
        live = call("video_models", {"refresh": True})["models"]
    except Exception as e:                                         # noqa: BLE001
        live = []
        print("   couldn't read Venice's list:", e)
    ids = [m["id"] for m in live if UNC_VIDEO_RX.search(m["id"]) and re.search(r"(text|image)-to-video$", m["id"])]
    ids += [i for i in ALSO if i not in ids]
    only = os.environ.get("ONLY", "").split()
    ids = [i for i in ids if i in only] if only else ids
    print(f"   candidates: {len(ids)} — {', '.join(ids) or 'none'}")
    for mid in ids:
        i2v = "image-to-video" in mid
        row = {"model": mid, "kind": "picture→video" if i2v else "words→video", "quote": None, "verdict": "", "usd": 0.0,
               "seconds": 0, "file": "", "note": ""}
        spec = next((m for m in live if m["id"] == mid), {})
        sizes = [r for r in spec.get("resolutions") or [] if re.fullmatch(r"\d{3,4}[pP]", str(r))]
        tries = (["720p"] if not sizes or "720p" in sizes else []) + [str(r).lower() for r in sizes] + ["768p", "1080p", "480p"]
        args = {"model": mid, "duration": f"{SECS}s", "resolution": tries[0]}
        if i2v:
            if not pic:
                row["verdict"] = "⏭ skipped"; row["note"] = "no first frame"; videos.append(row); continue
            args["image_b64"] = base64.b64encode(pic.read_bytes()).decode()
        else:
            args["aspect_ratio"] = "9:16"
        err = ""
        for res in list(dict.fromkeys(tries)):
            args["resolution"] = res
            try:
                q = call("video_quote", args)
                row["quote"], row["fits"] = float(q["usd"]), bool(q.get("fits", True))
                row["note"] = f"{q.get('duration')} {q.get('resolution')}"
                args["duration"], args["resolution"] = q.get("duration") or args["duration"], q.get("resolution") or res
                break
            except Exception as e:                                 # noqa: BLE001
                err = str(e)
                if "resolution" not in err:
                    break
        if row["quote"] is None:
            row["verdict"], row["note"] = "💥 no price", err[:200]
            print(f"  💥 no price {mid}: {err[:140]}")
        row["_args"] = args
        videos.append(row)
    spent, capped = 0.0, False
    for row in sorted([v for v in videos if v["quote"] is not None], key=lambda v: v["quote"]):
        args = row.pop("_args")
        why = ("over the daily video cap — run again tomorrow" if capped or not row.get("fits", True) else
               f"would pass the ${BUDGET:.2f} sweep budget" if spent + row["quote"] > BUDGET else "")
        if why:
            row["verdict"] = "⏭ skipped"; row["note"] += " · " + why
            print(f"  ⏭ skipped {row['model']} (${row['quote']:.2f}) — {why}"); continue
        print(f"  🎬 {row['model']} (${row['quote']:.2f}) …", flush=True)
        t0 = time.time()
        try:
            for attempt in (1, 2):                                 # one retry for a dropped connection (not a refusal)
                st = call("video_make", dict(args, prompt=prompt, negative_prompt=video.NO_TEXT_VIDEO,
                                             name=f"sweep-{row['model']}"[:40], task="model-sweep"))
                j = {"state": "running"}
                while time.time() - t0 < 900:
                    j = call("job_get", {"key": st["key"]})
                    if j.get("state") != "running":
                        break
                    time.sleep(5)
                m1 = (j.get("error") or {}).get("message") or ""
                if attempt == 1 and j.get("state") != "done" and re.search(r"urlopen|EOF|timed out|reset|temporar", m1, re.I):
                    print("     connection dropped — trying once more"); time.sleep(8); continue
                break
            row["seconds"] = int(time.time() - t0)
            res = j.get("result") or {}
            if j.get("state") == "done" and res.get("path"):
                dst = OUT / f"{row['model']}.mp4"
                shutil.copyfile(res["path"], dst)
                row.update(verdict="✅ made", usd=float(res.get("usd") or row["quote"]), file=str(dst.relative_to(ROOT)))
                spent += row["usd"]
            else:
                msg = ((j.get("error") or {}).get("message") or j.get("state") or "nothing came back")
                row["verdict"] = "❌ refused" if re.search(r"422|content violation|terms", msg, re.I) else "💥 failed"
                row["note"] += " · " + msg[:160]
        except Exception as e:                                     # noqa: BLE001
            row["seconds"] = int(time.time() - t0)
            row["verdict"] = "❌ refused" if re.search(r"422|content violation|terms", str(e), re.I) else "💥 failed"
            row["note"] += " · " + str(e)[:160]
            if "over_cap" in str(e):
                capped, row["verdict"] = True, "⏭ skipped"
        print(f"     {row['verdict']} {row['seconds']} s ${row['usd']:.2f} {row['note']}")
    for v in videos:
        v.pop("_args", None)
    (OUT / "results.json").write_text(json.dumps({"words": WORDS, "prompt": prompt, "first_frame": pic.name if pic else "",
                                                  "writers": writers, "videos": videos, "video_usd": round(spent, 4)}, indent=1))

# ---------- 3. scorecard ----------
L = [f"# 🧪 Model sweep — {STAMP}", "", f"**Words:** {WORDS}", ""]
if writers:
    L += ["## ✍️ Writers (motion detail)", ""]
    for w in sorted(writers, key=lambda w: (not w["verdict"].startswith("✅"), w["ms"])):
        L += [f"- **{w['verdict']}** `{w['provider']}/{w['model']}` — {w['ms'] / 1000:.1f} s · ${w['usd']:.4f} · {w['words']} words"
              + (f" · {w['note']}" if w["note"] else ""), f"  - wrote: {w['text'][:400] or '—'}"]
    L.append("")
if videos:
    L += ["## 🎬 Video models", "", f"Same prompt and same first frame for all. Spent: **${sum(v['usd'] for v in videos):.2f}**", ""]
    for v in videos:
        L += [f"- **{v['verdict'] or '—'}** `{v['model']}` ({v['kind']}) — quote "
              + (f"${v['quote']:.2f}" if v["quote"] is not None else "n/a") + f" · {v['seconds']} s · {v['note']}"
              + (f"\n  - file: `{v['file']}`\n  - looked right? ☐ yes ☐ softened ☐ wrong  ← **you judge this; the script can't see the clip**" if v["file"] else "")]
    L.append("")
card = ROOT / "docs" / f"SWEEP_{STAMP}.md"
card.parent.mkdir(parents=True, exist_ok=True)
card.write_text("\n".join(L) + "\n")
print(f"\n== scorecard: {card}\n== clips:     {OUT}")
PY

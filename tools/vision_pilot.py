#!/usr/bin/env python3
"""👁 Vision pilot (eyes+story+rip M0, 2026-11-25) — which model should be the Lab's eyes?

Run on gandalf:   python3 ~/ailab/tools/vision_pilot.py
                  python3 ~/ailab/tools/vision_pilot.py --models qwen3.5:4b,qwen3.5:9b,qwen3-vl:4b   # after a pull
Each model looks at 6 of his pictures (kept ones first, then the newest) and (1) describes it, (2) answers three
yes/no points the way M1 will. One page comes out: picture on top, the models side by side under it — time, card
memory, and a plain 🚫 when a model refused. $0, nothing leaves gandalf. Models not pulled are skipped, never pulled.
"""
from __future__ import annotations
import argparse, base64, html, io, json, re, subprocess, time, urllib.request
from pathlib import Path

OLLAMA, COMFY = "http://127.0.0.1:11434", "http://127.0.0.1:8188"
DATA = Path.home() / "hermes-data" / "ailab"
REFUSE = re.compile(r"\b(i can(?:'|no)t|i cannot|i'm unable|i am unable|i won't|not able to (?:help|describe|assist)|"
                    r"can't assist|cannot assist|against my|content policy|i'm sorry, but|inappropriate)\b", re.I)
CAPTION = ("Describe this picture plainly and completely for an artist: who or what is in it, how many, pose, clothing "
           "or nudity, setting, light, art style. Say exactly what you see; do not judge it. 3 sentences.")
POINTS = ["Is there any written text, caption, logo or watermark anywhere on the picture?",
          "Is there exactly one person or creature in the picture?",
          "Is the picture a photograph (not a drawing or painting)?"]


def _post(url: str, body: dict, timeout: float) -> dict:
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read() or b"{}")


def _get(url: str, timeout: float = 5) -> dict:
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read() or b"{}")


def vram_mb() -> int:
    try:
        out = subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                             capture_output=True, text=True, timeout=10).stdout
        return int(out.strip().splitlines()[0])
    except Exception:                                            # noqa: BLE001
        return -1


def small(p: Path, side: int) -> bytes:
    try:
        from PIL import Image
        im = Image.open(p).convert("RGB"); im.thumbnail((side, side))
        b = io.BytesIO(); im.save(b, "JPEG", quality=85); return b.getvalue()
    except Exception:                                            # noqa: BLE001 — no Pillow: send the file as it is
        return p.read_bytes()


def pick(project: str, n: int) -> list[tuple[Path, str]]:
    """Kept pictures first (with the prompt that made them), then the newest in the project."""
    root, out, seen = DATA / project, [], set()
    try:
        for x in reversed(json.loads((root / ".shelf" / "shelf.json").read_text()).get("kept", [])):
            for f in x.get("files") or []:
                p = root / f
                if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp") and p.exists() and p not in seen:
                    out.append((p, str(x.get("task") or "").split("\n")[0])); seen.add(p)
    except Exception:                                            # noqa: BLE001
        pass
    for p in sorted((root / "pictures").glob("*.*"), key=lambda q: q.stat().st_mtime, reverse=True):
        if len(out) >= n:
            break
        if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp") and p not in seen:
            out.append((p, "")); seen.add(p)
    return out[:n]


def ask(model: str, img64: str, q: str, tokens: int) -> tuple[str, float]:
    t = time.time()
    r = _post(f"{OLLAMA}/api/chat", {"model": model, "stream": False, "think": False, "keep_alive": "2m",
                                     "options": {"temperature": 0.2, "num_predict": tokens},
                                     "messages": [{"role": "user", "content": q, "images": [img64]}]}, 300)
    return str((r.get("message") or {}).get("content") or "").strip(), time.time() - t


def run_model(model: str, pics: list[tuple[Path, str]], dry: bool) -> list[dict]:
    rows = []
    for p, _task in pics:
        row = {"model": model, "pic": p.name, "caption": "", "secs": 0.0, "vram": -1, "refused": False, "points": [], "err": ""}
        if dry:
            row.update(caption="(dry run — no model called)", points=["—"] * len(POINTS)); rows.append(row); continue
        try:
            img = base64.b64encode(small(p, 1024)).decode()
            row["caption"], row["secs"] = ask(model, img, CAPTION, 220)
            row["vram"] = vram_mb()
            for q in POINTS:
                a, s = ask(model, img, q + " Answer with one word: yes or no.", 8)
                row["points"].append(a[:12]); row["secs"] += s
            row["refused"] = bool(REFUSE.search(row["caption"])) or not row["caption"]
        except Exception as e:                                   # noqa: BLE001
            row["err"] = f"{type(e).__name__}: {e}"[:200]
        rows.append(row); print(f"  {model:14} {p.name[:40]:40} {row['secs']:5.1f}s {'🚫' if row['refused'] else ''}{row['err']}")
    if not dry:
        try: _post(f"{OLLAMA}/api/generate", {"model": model, "keep_alive": 0}, 30)      # hand the card back
        except Exception: pass                                   # noqa: BLE001,E701
    return rows


CSS = """body{margin:0;font:19px/1.5 system-ui;background:#f5f2ec;color:#1d2733}body.d{background:#0d1520;color:#e8dfc8}
nav{position:sticky;top:0;background:inherit;padding:10px 14px;border-bottom:1px solid #b9b09c;display:flex;gap:10px;align-items:center}
button{font:inherit;padding:8px 14px;border-radius:10px;border:1px solid #8a8272;background:transparent;color:inherit;min-height:48px}
main{padding:12px;max-width:820px;margin:auto}img{width:100%;border-radius:12px}h2{font-size:21px;margin:26px 0 8px}
.c{border:1px solid #b9b09c;border-radius:12px;padding:12px;margin:10px 0;background:#ece6d8}body.d .c{background:#162233;border-color:#3a4a5e}
.m{font-weight:700}.s{opacity:.8;font-size:17px}.r{background:#ead9cf}body.d .r{background:#3a2420}table{width:100%;border-collapse:collapse}td{padding:6px;border-bottom:1px solid #b9b09c}"""


def page(pics, rows, models, skipped) -> str:
    by = {(r["model"], r["pic"]): r for r in rows}
    h = [f"<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'><title>👁 Vision pilot</title><style>{CSS}</style>",
         "<nav><b>👁 Vision pilot</b><button onclick=\"document.body.classList.toggle('d');try{localStorage.vp=document.body.className}catch(e){}\">🌙 / ☀️</button></nav>",
         "<script>try{document.body.className=localStorage.vp||''}catch(e){}</script><main><h2>Totals</h2><table>"]
    for m in models:
        rs = [r for r in rows if r["model"] == m]
        ok = [r for r in rs if not r["err"]]
        avg = sum(r["secs"] for r in ok) / len(ok) if ok else 0
        h.append(f"<tr><td class=m>{html.escape(m)}</td><td>{avg:.0f} s / picture</td><td>card {max([r['vram'] for r in rs] or [-1])} MB</td>"
                 f"<td>🚫 {sum(r['refused'] for r in rs)} refused</td><td>⚠️ {len(rs) - len(ok)} failed</td></tr>")
    h.append("</table>" + (f"<p class=s>Not pulled, skipped: {html.escape(', '.join(skipped))}</p>" if skipped else ""))
    h.append("<p class=s>Yes/no points asked: " + " · ".join(f"{i + 1}) {html.escape(q)}" for i, q in enumerate(POINTS)) + "</p>")
    for p, task in pics:
        h.append(f"<h2>{html.escape(p.name[16:60])}</h2><img src='data:image/jpeg;base64,{base64.b64encode(small(p, 640)).decode()}'>")
        if task:
            h.append(f"<p class=s>His prompt: {html.escape(task)}</p>")
        for m in models:
            r = by.get((m, p.name))
            if not r:
                continue
            body = html.escape(r["err"] or r["caption"])
            h.append(f"<div class='c{' r' if r['refused'] or r['err'] else ''}'><div class=m>{html.escape(m)} {'🚫 refused' if r['refused'] else ''}</div>"
                     f"<div>{body}</div><div class=s>{r['secs']:.0f} s · card {r['vram']} MB · points: {html.escape(' / '.join(r['points']))}</div></div>")
    return "".join(h) + "</main>"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", default="qwen3.5:4b,qwen3.5:9b,qwen3-vl:4b")
    ap.add_argument("--project", default="image-testing"); ap.add_argument("--n", type=int, default=6)
    ap.add_argument("--dry", action="store_true"); ap.add_argument("--out", default="")
    a = ap.parse_args()
    want = [m.strip() for m in a.models.split(",") if m.strip()]
    pics = pick(a.project, a.n)
    if not pics:
        raise SystemExit(f"No pictures in {DATA / a.project / 'pictures'} 👉 make or keep one in the Lab first, or pass --project")
    have = want if a.dry else []
    if not a.dry:
        try:
            tags = {m["name"] for m in _get(f"{OLLAMA}/api/tags").get("models", [])}
        except Exception as e:                                   # noqa: BLE001
            raise SystemExit(f"Ollama isn't answering ({e}) 👉 start it: systemctl start ollama") from e
        have = [m for m in want if m in tags or m + ":latest" in tags]
        try: _post(f"{COMFY}/free", {"unload_models": True, "free_memory": True}, 10)     # ComfyUI lets go of the card
        except Exception: pass                                   # noqa: BLE001,E701
    skipped = [m for m in want if m not in have]
    print(f"{len(pics)} pictures · models: {have} · skipped (not pulled): {skipped}")
    rows = [r for m in have for r in run_model(m, pics, a.dry)]
    out = Path(a.out) if a.out else DATA / "_pilot" / f"vision_pilot_{time.strftime('%Y%m%d-%H%M')}.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page(pics, rows, have, skipped), encoding="utf-8")
    out.with_suffix(".json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
    print(f"\n👁 Page: {out}\n   open it: xdg-open {out}")


if __name__ == "__main__":
    main()

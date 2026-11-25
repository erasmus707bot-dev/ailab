"""📝 Document runs (2026-11-24, Scott: "the same kind of work … so I may make my art in … document … forms").

A run whose chips are 📝 Text (optionally + 🖼 Image), with nothing app-like or video on, skips the step-by-step agent:
❓ length · tone · pictures · file types → ✍️ an uncensored writer (Venice first) writes the whole piece — Scott's own
words and any text he gives are used exactly, never softened → optional pictures (Lustify, safe mode off, no text on
them) placed under the title or under each section → docs/<name>.md, plus Word (.docx, pandoc) and PDF (LibreOffice)
when those are on this computer. The doc and its pictures stay in this project (📍 Where shows the folders).
"""
from __future__ import annotations

import re
import shutil
import subprocess

from . import creation, makers, picture

DOC_SYS = ("You write for Scott: stories, articles, letters, scripts, poems, notes — whatever he asks. " + makers.KEEP_WORDS +
           " If he gives text to include, it goes in word for word. Write the full piece, not an outline. Markdown: one "
           "'# ' title line, then '## ' section headings when the piece has parts. Plain words, short paragraphs. Reply "
           "ONLY with the document — no notes to him before or after.")
LENGTH_TOKENS = {"short": 1200, "medium": 3500, "long": 8000}
PIC_Q = ["Pictures in it?", ["No pictures ⭐", "One under the title", "One per section (up to 4)"]]
FILES_Q = ["Also save as?", ["Word + PDF ⭐", "Just the text file (.md)"]]
MAX_SECTION_PICS = 4


def _questions() -> list:
    ty = next(iter(creation.pick(["text"])), {}) or {}
    return list(ty.get("questions") or []) + [PIC_Q, FILES_Q]


def tokens_for(choice: str) -> int:
    c = (choice or "").lower()
    return next((v for k, v in LENGTH_TOKENS.items() if k in c), 1200)


def title_of(md: str, fallback: str) -> str:
    m = re.search(r"^#\s+(.+)$", md, re.M)
    return (m.group(1).strip() if m else fallback)[:80]


def sections(md: str) -> list[tuple[int, str]]:
    """(line index, heading text) for each '## ' heading."""
    return [(i, ln[3:].strip()) for i, ln in enumerate(md.splitlines()) if ln.startswith("## ")]


def place_pictures(md: str, pics: list[tuple[int, str]]) -> str:
    """Put ![](path) lines after the given line indexes (−1 = after the title)."""
    lines = md.splitlines()
    title = next((i for i, ln in enumerate(lines) if ln.startswith("# ")), -1)
    at: dict[int, list[str]] = {}
    for idx, rel in pics:
        at.setdefault(title if idx < 0 else idx, []).append(f"\n![]({rel})\n")
    out = []
    for i, ln in enumerate(lines):
        out.append(ln)
        out += at.get(i, [])
    if -1 in at:                                             # no title line: pictures go first
        out = at[-1] + out
    return "\n".join(out) + "\n"


def export(md_path, want: bool) -> tuple[list[str], str]:
    """(.docx/.pdf paths made, note). pandoc for Word, LibreOffice for PDF (from the .docx) — whichever are here."""
    if not want:
        return [], ""
    made, notes = [], []
    pandoc, soffice = shutil.which("pandoc"), shutil.which("soffice") or shutil.which("libreoffice")
    docx = md_path.with_suffix(".docx")
    if pandoc:
        r = subprocess.run([pandoc, md_path.name, "-o", docx.name, "--resource-path", "."], cwd=md_path.parent,
                           capture_output=True, text=True, timeout=120)
        if r.returncode == 0 and docx.is_file():
            made.append(docx)
        else:
            notes.append(f"Word failed: {r.stderr[-160:]}")
    else:
        notes.append("Word needs pandoc on this computer (sudo apt install pandoc)")
    if soffice and docx.is_file():
        try:
            r = subprocess.run([soffice, "--headless", "--convert-to", "pdf", "--outdir", str(md_path.parent), str(docx)],
                               capture_output=True, text=True, timeout=180)
            pdf = md_path.with_suffix(".pdf")
            (made.append(pdf) if pdf.is_file() else notes.append(f"PDF failed: {r.stderr[-160:]}"))
        except (OSError, subprocess.TimeoutExpired) as e:
            notes.append(f"PDF failed: {e}")
    elif not soffice:
        notes.append("PDF needs LibreOffice on this computer")
    return made, "; ".join(notes)


def run(run) -> None:
    words = picture.picture_words(run.task).strip()       # from a 🧱 build prompt: only his idea line
    ch = makers.ask(run, "doc", makers.items_from(_questions()))
    length, tone = ch.get("how long", ""), ch.get("tone", "")
    pics_pick, files_pick = ch.get("pictures in it", "No"), ch.get("also save as", "Word")
    extra = "\n".join(x for x in (f"Length: {length}" if length else "", f"Tone: {tone}" if tone else "") if x)
    run.cap_usd = max(run.cap_usd, 0.25)
    text, who = makers.write(run, DOC_SYS, words + ("\n\n" + extra if extra else ""), tokens_for(length),
                             "Writing your piece", "lab-doc")
    if not text:
        run._record({"action": "doc", "why": "📝 write it", "result": {"error": who}, "usd": 0.0})
        run.state, run.why = "failed", f"📝 No writer would write it ({who}). Try another model in the box."
        return
    run._check_stop()
    name = makers.slug(title_of(text, picture.own_words(words)), default="doc")
    st = makers.stamp()
    pics: list[tuple[int, str]] = []
    if not pics_pick.lower().startswith("no") and run.connected:
        want = [(-1, title_of(text, words))] if "title" in pics_pick.lower() else sections(text)[:MAX_SECTION_PICS]
        want = want or [(-1, title_of(text, words))]
        mine = picture.own_words(words)[:400]
        for n, (idx, head) in enumerate(want, 1):
            run._check_stop()
            made = makers.make_picture(run, f"{mine}. {head}. Illustration for this part of the story.", "16:9",
                                       f"pictures/{st}-{name}-{n}", f"picture {n} of {len(want)}")
            if made.get("error"):
                run._record({"action": "picture", "why": f"🎨 picture {n}", "result": {"error": made["error"]}, "usd": 0.0})
                continue
            pics.append((idx, "../" + made["path"]))
    elif not pics_pick.lower().startswith("no"):
        run._record({"action": "picture", "why": "🎨 pictures skipped", "result": {"note": "🔌 pictures need connected mode"}, "usd": 0.0})
    md = place_pictures(text, pics) if pics else text.rstrip() + "\n"
    rel = picture.claim(run.root, f"docs/{st}-{name}.md")
    p = run.root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(md)
    run.docs = (getattr(run, "docs", None) or []) + [{"path": rel, "kind": "doc", "writer": who}]
    run._record({"action": "doc", "path": rel, "why": f"📝 wrote it with {makers.short(who)}",
                 "result": {"bytes": len(md), "pictures": len(pics), "writer": who}, "usd": 0.0})
    if not files_pick.lower().startswith("just"):
        picture.stage(run, "📄", "Saving Word and PDF copies")
    made, note = export(p, not files_pick.lower().startswith("just"))
    for f in made:
        r2 = str(f.relative_to(run.root))
        run.docs.append({"path": r2, "kind": "doc"})
        run._record({"action": "doc", "path": r2, "why": f"📄 saved {f.suffix[1:].upper()} copy", "result": {}, "usd": 0.0})
    run.state = "done"
    run.why = (f"📝 Written with {makers.short(who)}" + (f", {len(pics)} picture{'s' if len(pics) != 1 else ''}" if pics else "")
               + f". Saved in {rel}" + (" + " + ", ".join(f.suffix[1:].upper() for f in made) if made else "")
               + (f". ({note})" if note else "."))
    picture.stage(run, "✅", "Done")

"""🧹 Remodel M3 (Scott 2026-11-25, pick 1): ✏️ Change this from any 📚 Library item · ⚖️ Compare two ·
the 🪄 improver learns from what he ✅ kept and 🗑 threw away."""
import tempfile
from pathlib import Path

from ailab import shelf
from ailab.server import App

HTML = (Path(__file__).resolve().parent.parent / "ailab" / "web" / "index.html").read_text()


def test_improver_sees_kept_and_thrown_prompts():
    d = Path(tempfile.mkdtemp())
    shelf.keep(d, "r1", "a red fox by a lake\nLook: Oil painting", [])
    shelf.keep(d, "r2", "a red fox by a lake\nChange: at dawn", [])          # same first line → listed once
    shelf.toss(d, "r3", "a grey city street", [])
    taste = App._taste(d)
    assert taste == {"kept": ["a red fox by a lake"], "tossed": ["a grey city street"]}
    m = App._improve_msgs(App, {"ctypes": ["image"]}, "a wolf", taste)[1]["content"]
    assert m.startswith("His words: a wolf")
    assert "Prompts he kept in this project" in m and "a red fox by a lake" in m
    assert "Prompts he threw away (do not steer toward these): a grey city street" in m


def test_no_taste_yet_changes_nothing():
    assert App._improve_msgs(App, {}, "a wolf", {"kept": [], "tossed": []})[1]["content"] == "His words: a wolf"
    assert App._taste(Path(tempfile.mkdtemp())) == {"kept": [], "tossed": []}


def test_library_can_change_and_compare():
    for must in ("function libraryBox(p, hooks)", "/api/shelf/source?project=", "✏️ Change this", 'id: "libcmpbtn"', "⚖️ Side by side",
                 "hooks.change(task, ids)", "ag.startWith(task, ids, false)", "🧠 learned from"):
        assert must in HTML, must
    i = HTML.index("function changeBox2(f, k)")
    body = HTML[i:HTML.index("function showCmp()", i)]
    assert "The Lab no longer has the words this was made from" in body      # no made-up prompt for an old picture
    assert 'ids = ["edit"]' in body                                           # a page/doc change is an 🔧 edit, not a new picture

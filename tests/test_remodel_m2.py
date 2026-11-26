"""🧹 Remodel M2 + M2b (Scott 2026-11-25, pick 1): ✅ Keep & start new · 🗑 Throw away (hidden, back for 30 days) ·
📚 Library shows #N and the thrown-away list · a build on a 🔓 model asks who writes the code."""
import tempfile
import time
import unittest
from pathlib import Path

from ailab import shelf

HTML = (Path(__file__).resolve().parent.parent / "ailab" / "web" / "index.html").read_text()


def _proj():
    d = Path(tempfile.mkdtemp())
    (d / "pictures").mkdir()
    (d / "pictures" / "a.png").write_bytes(b"A")
    (d / "index.html").write_text("old page")
    return d


MADE = [{"path": "pictures/a.png", "kind": "picture", "new": True}, {"path": "index.html", "kind": "page", "new": False}]


class Shelf(unittest.TestCase):
    def test_keep_numbers_up_and_is_the_same_twice(self):
        d = _proj()
        a = shelf.keep(d, "r1", "a fox", MADE)
        self.assertEqual((a["n"], a["files"]), (1, ["pictures/a.png", "index.html"]))
        self.assertEqual(shelf.keep(d, "r1", "a fox", MADE)["n"], 1)
        self.assertEqual(shelf.keep(d, "r2", "a lake", [])["n"], 2)
        self.assertEqual([x["n"] for x in shelf.view(d)["kept"]], [1, 2])

    def test_throw_away_hides_only_what_the_run_created_and_comes_back(self):
        d = _proj()
        shelf.keep(d, "r1", "a fox", MADE)
        it = shelf.toss(d, "r1", "a fox", MADE, ["index.html"])
        self.assertEqual(it["files"], ["pictures/a.png"])                       # the changed page is not moved
        self.assertFalse((d / "pictures" / "a.png").exists())
        self.assertEqual((d / ".shelf" / "trash" / "r1" / "pictures" / "a.png").read_bytes(), b"A")   # hidden, not deleted
        self.assertEqual((d / "index.html").read_text(), "old page")
        v = shelf.view(d)
        self.assertEqual((v["kept"], v["tossed"][0]["days_left"]), ([], 30))    # thrown away = no longer kept
        with self.assertRaises(ValueError):
            shelf.keep(d, "r1", "a fox", MADE)
        back = shelf.restore(d, "r1")
        self.assertEqual(back["files"], ["pictures/a.png"])
        self.assertEqual((d / "pictures" / "a.png").read_bytes(), b"A")
        self.assertEqual(shelf.view(d)["tossed"], [])

    def test_bring_back_never_overwrites(self):
        d = _proj()
        shelf.toss(d, "r1", "x", MADE)
        (d / "pictures" / "a.png").write_bytes(b"NEW")
        self.assertEqual(shelf.restore(d, "r1")["files"], ["pictures/a (restored).png"])
        self.assertEqual((d / "pictures" / "a.png").read_bytes(), b"NEW")

    def test_gone_for_good_only_after_30_days(self):
        d = _proj()
        shelf.toss(d, "r1", "x", MADE)
        now = time.time()
        self.assertEqual(shelf.purge(d, now + 29 * shelf.DAY), 0)
        self.assertTrue((d / ".shelf" / "trash" / "r1").exists())
        self.assertEqual(shelf.purge(d, now + 31 * shelf.DAY), 1)
        self.assertFalse((d / ".shelf" / "trash" / "r1").exists())

    def test_paths_outside_the_project_or_in_dot_folders_are_refused(self):
        d = _proj()
        for bad in ("../x.png", "/etc/passwd", ".shelf/shelf.json", "a/../../x", ""):
            self.assertIsNone(shelf._safe(d, bad), bad)
        self.assertEqual(shelf.toss(d, "r9", "x", [{"path": "../x.png", "new": True}])["files"], [])


def test_page_has_the_keep_loop_and_the_library_shows_it():
    for must in ('id: "wbkeep"', 'id: "wbtoss"', '"/api/shelf/keep"', '"/api/shelf/toss"', '"/api/shelf/restore"', "🆕 Keep & clear",
                 "🗑 Throw away", "🆕 Just clear", "↩ Bring back", '["kept", "✅ Kept"]', "Kept as #${r.item.n}"):
        assert must in HTML, must


def test_a_build_on_an_uncensored_model_asks_first():
    for must in ('id: "agcensor"', "function censorChoice()", "🔓 Stay uncensored ⭐", "🔒 Filtered coder, this run only", "async function doStart(model)",
                 "model: model || modelSel.value", 'store.get("censorstay." + p.id, false)'):
        assert must in HTML, must
    i = HTML.index("function censorChoice()")
    assert "store.set(\"model.\"" not in HTML[i:HTML.index("async function doStart(model)", i)]   # the card never changes his saved model

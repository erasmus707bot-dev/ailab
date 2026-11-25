"""🧹 Remodel M1 (2026-11-24, Scott: "too much going on with the workspace"): 🤖 Make | 👀 Stage, ⚙️ Options fold,
✨ starters on the empty Stage, 📚 Library, 🪄 prompt improvement cycle, 🔓 uncensored as the default."""
import tempfile
import unittest
from pathlib import Path

from ailab import preview
from ailab.server import App

HTML = (Path(__file__).resolve().parent.parent / "ailab" / "web" / "index.html").read_text()


def test_two_zones_and_the_folds():
    assert 'const PANES = ["agent", "code"]' in HTML
    assert 'paneBar("agent", "🤖 Make", sec, panes)' in HTML and 'paneBar("code", "👀 Stage", sec, panes)' in HTML
    for must in ('id: "agoptions"', 'id: "wbstarters"', 'id: "wbfinish"', 'id: "wbdetails"', 'id: "wblib"', 'id: "wbstagex"'):
        assert must in HTML, must
    assert '"✋ Waiting for you"' not in HTML                                 # the old middle-pane title is gone, not layered over


def test_nothing_was_lost_in_the_move():
    """Every control that left the left pane is still on the page."""
    for must in ('id: "goprompt"', 'id: "golive"', "ag.repoRow", "ag.goals", "ag.picker", "ag.askRow", "ag.batchRow", "ag.newBtn",
                 "ag.liveRow", "ag.held", "shipBar", "pv.tabs", "filesEd", "drawer", "wbResetLayout"):
        assert must in HTML, must


def test_results_show_once_on_the_stage():
    assert "if (wb) wb.onRun(run, stage);" in HTML and "stageExtra.replaceChildren(...extras)" in HTML
    assert "if (!wb) steps.append(stageCard(run));" in HTML                # the left pane no longer repeats the stage card
    assert HTML.count("madeBox.append(mc)") == 0                           # 📦 once, from the Stage extras
    assert "final.hidden = running || !run.why || !!wb" in HTML


def test_uncensored_is_the_default_and_filtered_is_a_choice():
    assert 'store.get("artonly", true)' in HTML and 'store.get("artonly", false)' not in HTML
    assert "limits === UNC) === uncOn" in HTML                              # first-time model = an uncensored one
    assert "const freeFirst = uncOn ||" in HTML
    assert "untick to allow 🔒 filtered models" in HTML


def test_improve_cycle_is_on_the_page():
    for must in ('id: "agimpbtn"', 'mode: "prompt"', "✓ Use it ⭐", "🔁 Again", "✏️ Fix it", "✗ Keep mine"):
        assert must in HTML, must


def test_library_lists_what_is_in_the_folder_newest_first():
    assert "function libraryBox(p" in HTML and "(b.mtime || 0) - (a.mtime || 0)" in HTML
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / "pictures").mkdir()
        (root / "pictures" / "a.png").write_bytes(b"x")
        rows = preview.list_root(root)
        assert rows[0]["path"] == "pictures/a.png" and isinstance(rows[0]["mtime"], int)


class Improve(unittest.TestCase):
    def test_improve_prompt_keeps_his_words_and_knows_the_kind(self):
        m = App._improve_msgs(App, {"ctypes": ["video", "image"]}, "a red fox by a lake")
        self.assertIn("a short video", m[0]["content"])
        self.assertIn("do not remove, soften or swap", m[0]["content"])
        self.assertEqual(m[1]["content"], "His words: a red fox by a lake")

    def test_next_round_carries_the_last_version_and_the_fix(self):
        m = App._improve_msgs(App, {"ctypes": ["website"], "previous": "v1", "fix": "shorter"}, "a shop page")
        self.assertIn("software an AI builder will make", m[0]["content"])
        self.assertIn("Your last version: v1", m[1]["content"])
        self.assertIn("He says to fix: shorter", m[1]["content"])
        again = App._improve_msgs(App, {"previous": "v1"}, "x")[1]["content"]
        self.assertIn("fresh, different take", again)

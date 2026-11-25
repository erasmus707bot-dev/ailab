"""🧹 2026-11-25 simplify: 🚪 clean start every open, 📚 all-projects Library, less on screen."""
from pathlib import Path

HTML = (Path(__file__).resolve().parents[1] / "ailab" / "web" / "index.html").read_text(encoding="utf-8")


def test_opens_on_clean_start():
    assert 'view = "welcome"; render();' in HTML
    assert "function welcomeView()" in HTML and "function freshStart(pid)" in HTML
    assert 'store.set("freshgo", 1)' in HTML and "ag.newBtn.click()" in HTML


def test_library_all_projects_default():
    assert 'id="libtop"' in HTML and 'go("library")' in HTML
    assert "function libraryAllView()" in HTML
    assert "!picked.length || picked.includes(it.project)" in HTML     # empty pick = all projects
    assert 'store.set("libgo"' in HTML and 'store.get("libgo", null)' in HTML


def test_less_on_screen():
    assert 'open: !!store.get("libopen", false)' in HTML               # per-project Library starts folded
    assert 'optNow), ag.batchRow' in HTML                 # batch folds into Options
    assert '"📜 Steps"' in HTML and '"🎯 More ways to start"' in HTML
    assert 'class: "cenline"' in HTML and "ℹ️ Why am I asked?" in HTML  # censor card = one line
    assert 'id="mode" title="Mode" hidden' in HTML

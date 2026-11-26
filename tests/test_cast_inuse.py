"""Live 2026-11-25: 🎭 Saved casts opened on "Mara & Dina" while the project used Aria & Ben — the picker opens on the
cast in use, marks it ✓, and ♻️ is off for it. Step counts: non-agent runs show a plain count (was "130/24 steps")."""
from pathlib import Path

HTML = (Path(__file__).resolve().parent.parent / "ailab" / "web" / "index.html").read_text()


def test_cast_picker_opens_on_the_cast_in_use():
    cp = HTML[HTML.index("function castPicker"):HTML.index("function stepsWords")]
    assert "selected: inUse(c)" in cp and '" ✓ in use"' in cp and '"✓ In use"' in cp and 'sel.addEventListener("change", mark)' in cp


def test_steps_words_plain_for_story_and_picture_runs():
    sw = HTML[HTML.index("function stepsWords"):HTML.index("function breakdownBox")]
    assert "run.picture || run.batch || run.video || run.docmode" in sw and "/${run.step_cap} steps" in sw
    assert "${stepsWords(run)} · $" in HTML and "/${run.step_cap} steps · $" not in HTML.replace(sw, "")

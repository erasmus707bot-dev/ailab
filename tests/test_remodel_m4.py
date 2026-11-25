"""🧹 Remodel M4 (2026-11-25): 🏁 Project done is a mark only · 📚 jump chip in the Stage bar · 🧠 line folded into the step log."""
import tempfile
from pathlib import Path

from ailab import shelf

HTML = (Path(__file__).resolve().parent.parent / "ailab" / "web" / "index.html").read_text()


def test_done_is_a_mark_that_survives_keep_and_can_be_taken_back():
    d = Path(tempfile.mkdtemp())
    assert shelf.view(d)["done_at"] == 0
    assert shelf.set_done(d, True) > 0
    shelf.keep(d, "r1", "a fox", [])                       # building on after "done" keeps the mark and the numbers
    v = shelf.view(d)
    assert v["done_at"] > 0 and [x["n"] for x in v["kept"]] == [1]
    assert shelf.set_done(d, False) == 0 and shelf.view(d)["kept"][0]["n"] == 1


def test_page_has_the_wrap_card_and_the_jump_chip():
    for must in ('id: "wblibjump"', 'id: "libdonebtn"', '"/api/shelf/done"', "🏁 Mark it done ⭐", "↩ Not done yet", "stageBar.querySelector(\"h2\").after(lib.jump)",
                 "ship: () => shipOpen(), where: showWhere, fresh: newProject", "if (ml && wb) log.append("):
        assert must in HTML, must

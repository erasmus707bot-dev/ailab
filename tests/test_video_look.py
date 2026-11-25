"""🎬🎨 Look for video (2026-11-25, Scott: "I need access to the mood/theme options")."""
from pathlib import Path

from ailab import looks, video

HTML = (Path(__file__).resolve().parent.parent / "ailab" / "web" / "index.html").read_text()
CAT = looks.catalog() if hasattr(looks, "catalog") else None


def _some_look():
    """Two real Look names from the catalog, whatever it holds today."""
    data = __import__("json").loads((Path(looks.__file__).parent / "looks.json").read_text())
    names = [it["n"] for tab in data["tabs"] for it in tab["items"]]
    return looks.normalize(names[:1] + names[-1:])[0]


def test_look_picker_shows_for_video_too():
    assert 'look.show(on.includes("image") || on.includes("video"))' in HTML


def test_his_words_stay_first_and_whole_and_the_look_is_added():
    look = _some_look()
    assert look
    mine = "a red fox runs along a lake"
    out = video.with_look(f"{mine}. The camera pushes in slowly", mine, look)
    assert out.startswith(mine)
    assert "The camera pushes in slowly" in out
    head, tail = looks.parts(look)
    assert all(w in out for w in head + tail)


def test_no_look_changes_nothing():
    assert video.with_look("a fox. slow pan", "a fox", []) == "a fox. slow pan"


def test_video_run_reads_the_look_line():
    src = Path(video.__file__).read_text()
    assert "looks.normalize(looks.from_task(words))" in src
    assert src.count("with_look(") >= 3                    # the helper + first frame + the clip prompt

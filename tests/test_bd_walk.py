"""🎬 Harvest → Lab (2026-11-25): #yours=bd:<id>:<scene> opens that scene's card and glows 🎬 Make one like this —
it never starts a run by itself (spend stays a tap)."""
from pathlib import Path

HTML = (Path(__file__).resolve().parent.parent / "ailab" / "web" / "index.html").read_text()


def test_bd_link_routes_before_other_yours_links():
    oy = HTML[HTML.index("async function openYours()"):]
    assert oy.index("yours=bd:(bd-[0-9a-f]{16})") < oy.index("yours=rebuild:") < oy.index(r"yours=\w+:")


def test_walk_opens_the_scene_and_only_glows():
    w = HTML[HTML.index("function bdWalk(m)"):HTML.index("async function openYours()")]
    assert 'box.open(id, sc)' in w and '`bd-${id}-${sc}`' in w and 'classList.add("yours")' in w
    assert ".click()" not in w and "/api/breakdown/make" not in w          # he taps 🎬 himself
    assert 'store.get("project")' in w and "Open a project first" in w
    assert "box.open = openSheet;" in HTML

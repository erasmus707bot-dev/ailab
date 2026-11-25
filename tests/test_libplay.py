"""▶ 2026-11-25 Library player: ◀ ▶ click-through, ▶ Slideshow, 🎬 Play videos, 📝 Writing & pages — both Libraries."""
from pathlib import Path

HTML = (Path(__file__).resolve().parents[1] / "ailab" / "web" / "index.html").read_text(encoding="utf-8")


def test_player_exists_with_toggles():
    assert "function libPlayer(o)" in HTML
    for k in ('"libplay.on"', '"libplay.vids"', '"libplay.docs"', '"libplay.secs"'):
        assert k in HTML                                   # every toggle persists
    assert "▶ Slideshow" in HTML and "🎬 Play videos" in HTML and "📝 Writing & pages" in HTML
    assert 'store.get("libplay.docs", false)' in HTML      # writing & pages off by default (Scott pick 1)


def test_videos_play_through_then_advance():
    assert "body.onended = () => { if (on && vids" in HTML
    assert "(k === \"vid\" && vids)" in HTML                # off = slideshow skips videos
    assert "b.onplaying = () => clearTimeout(timer)" in HTML and "}, 15000);" in HTML   # stuck video is skipped


def test_both_libraries_use_it():
    assert HTML.count("libPlayer({") == 2
    assert HTML.count("pl.bar()") == 2 and HTML.count("pl.hook(body, k)") == 2
    assert HTML.count("pl.stop()") == 2                     # closing stops the timer


def test_phone_and_keys():
    assert '"touchend"' in HTML and '"ArrowRight"' in HTML
    assert ".libplay .btn, .libplay .tchip, .libplay select { min-height: 44px" in HTML

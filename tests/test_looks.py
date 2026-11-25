"""🎨 Picture Looks (2026-11-24): catalog, limits, clashes, prompt order, saved/last Looks, picture-run wiring."""
from __future__ import annotations

import json
import threading

from ailab import agent, config, looks
from tests.test_agent import Base
from tests.test_picture import PicMCP
from tests.test_agent import Brain
from tests.test_workflow import wait_for


class Catalog(Base):
    def test_catalog_shape_and_unique_names(self):
        cat = looks.catalog()
        ids = [t["id"] for t in cat["tabs"]]
        self.assertEqual(ids, ["medium", "study", "figure", "style", "theme", "mood", "light", "colour", "camera", "era", "finish"])
        names = [it["n"].lower() for t in cat["tabs"] for it in t["items"]]
        self.assertEqual(len(names), len(set(names)), "chip names must be unique across tabs")
        self.assertGreaterEqual(len(names), 140)
        self.assertTrue(all("·" not in n and "," not in n and ";" not in n for n in names))
        self.assertEqual(next(t for t in cat["tabs"] if t["id"] == "medium")["max"], 1)
        known = set(names)
        for a, bs in cat["clash"]:
            self.assertIn(a.lower(), known)
            for b in bs.split("|"):
                self.assertIn(b.lower(), known, b)

    def test_override_file_replaces_a_tab_and_hides_one(self):
        (config.home()).mkdir(parents=True, exist_ok=True)
        (config.home() / "looks.json").write_text(json.dumps({"tabs": [
            {"id": "era", "label": "Era", "items": [{"n": "Bronze age"}]}, {"id": "finish", "off": True}]}))
        cat = looks.catalog()
        self.assertEqual([it["n"] for it in next(t for t in cat["tabs"] if t["id"] == "era")["items"]], ["Bronze age"])
        self.assertNotIn("finish", [t["id"] for t in cat["tabs"]])


class Limits(Base):
    def test_medium_one_others_three_eight_total(self):
        kept, notes = looks.normalize(["oil painting", "Watercolor", "Moody", "Serene", "Joyful", "Romantic", "Eerie"])
        self.assertEqual(kept, ["Oil painting", "Moody", "Serene", "Joyful"])
        self.assertTrue(any("Watercolor" in n and "1 Medium pick" in n for n in notes))
        self.assertTrue(any("Romantic" in n and "3 Mood picks" in n for n in notes))
        self.assertTrue(any("Eerie" in n for n in notes))

    def test_unknown_names_kept_and_counted(self):
        many = ["Photo", "Golden hour", "Warm", "Close-up", "1950s", "Grainy", "Portrait", "Serene", "my own words"]
        kept, notes = looks.normalize(many)
        self.assertEqual(len(kept), 8)
        self.assertIn("8 picks at most", notes[0])
        kept, _ = looks.normalize(["dusty rose tint"])
        self.assertEqual(kept, ["dusty rose tint"])

    def test_clash_is_a_soft_note(self):
        self.assertEqual(looks.clashes(["Photo", "Watercolor"]), ["Photo + Watercolor"])
        self.assertEqual(looks.clashes(["High-key", "Low-key", "Warm"]), ["High-key + Low-key"])
        self.assertEqual(looks.clashes(["Oil painting", "Moonlight"]), [])


class Prompt(Base):
    def test_order_words_head_detail_tail(self):
        p = looks.assemble("a fox in the snow", ["Golden hour", "Oil painting", "Serene", "Impressionism"], "pine trees behind")
        self.assertTrue(p.startswith("a fox in the snow. oil painting, visible brushstrokes, impressionist style. pine trees behind. "))
        self.assertTrue(p.endswith("serene mood, golden hour light."))

    def test_line_round_trip(self):
        task = "a cabin\nLook: Oil painting · Moody, Golden hour\nShape: Wide (screen)"
        self.assertEqual(looks.from_task(task), ["Oil painting", "Moody", "Golden hour"])
        self.assertEqual(looks.strip_line(task), "a cabin\nShape: Wide (screen)")
        self.assertEqual(looks.line(["A", "B"]), "Look: A · B")
        self.assertEqual(looks.from_task("no look here"), [])

    def test_limit_cuts_only_writer_detail_then_tail(self):
        mine = "x" * 1300
        p = looks.assemble(mine, ["Photo", "Golden hour"], "word " * 100, limit=1400)
        self.assertLessEqual(len(p), 1400)
        self.assertTrue(p.startswith(mine + ". photograph, photorealistic."))
        self.assertIn("golden hour light", p)
        p = looks.assemble("y" * 1390, ["Photo", "Golden hour"], "", limit=1400)
        self.assertNotIn("golden", p)                       # tail dropped before Scott's words are ever cut
        self.assertTrue(p.startswith("y" * 1390))

    def test_no_double_words(self):
        p = looks.assemble("a cat", ["Golden hour"], "bathed in golden hour light")
        self.assertEqual(p.lower().count("golden hour light"), 1)

    def test_negative_pushes_photo_away_for_drawn_looks(self):
        self.assertTrue(looks.negative(["Watercolor"], "text").endswith(looks.NOT_PHOTO))
        self.assertTrue(looks.negative(["Comic book", "Moonlight"], "text").endswith(looks.NOT_PHOTO))
        self.assertEqual(looks.negative(["Photo", "Golden hour"], "text"), "text")
        self.assertEqual(looks.negative(["Golden hour"], "text"), "text")
        self.assertEqual(looks.negative([], "text"), "text")

    def test_photo_and_style_flags(self):
        self.assertTrue(looks.photo(["Photo"]))
        self.assertTrue(looks.has_look_style(["Anime"]))
        self.assertFalse(looks.has_look_style(["Moonlight"]))


class Saved(Base):
    def test_save_replace_delete_last(self):
        self.assertFalse(looks.save("", ["Photo"])["ok"])
        self.assertFalse(looks.save("Empty", [])["ok"])
        looks.save("Moody oil", ["Oil painting", "Low-key"])
        r = looks.save("moody OIL", ["Watercolor"])                      # same name, any case → replaced, newest first
        self.assertEqual(r["saved"], [{"name": "moody OIL", "look": ["Watercolor"]}])
        looks.save("Anime", ["Anime", "Vibrant"])
        self.assertEqual([s["name"] for s in looks.saved()["saved"]], ["Anime", "moody OIL"])
        looks.delete("anime")
        self.assertEqual([s["name"] for s in looks.saved()["saved"]], ["moody OIL"])
        looks.remember_last(["Photo", "Golden hour"])
        self.assertEqual(looks.public()["last"], ["Photo", "Golden hour"])
        self.assertIn("tabs", looks.public())


class LookRun(Base):
    def make(self, mcp, task, ask=False, replies=("soft snow falling, pine trees",)):
        b = Brain(list(replies))
        b.mcp = mcp
        return agent.Run(b, config.load({"mode": "connected"}), self.project, "openrouter", "m", task, ctypes=["image"], ask_first=ask), b

    def test_look_reaches_the_model_in_order_and_is_saved_on_the_picture(self):
        mcp = PicMCP()
        r, b = self.make(mcp, "a fox in the snow\nLook: Watercolor · Serene · Golden hour")
        r.loop()
        self.assertEqual(r.state, "done", r.why)
        args = mcp.args[mcp.calls.index("image_make")]
        self.assertTrue(args["prompt"].startswith("a fox in the snow. watercolor painting, soft washes, paper texture. soft snow"), args["prompt"])
        self.assertTrue(args["prompt"].endswith("serene mood, golden hour light."))
        self.assertNotIn("Look:", args["prompt"])
        self.assertIn("Look: Watercolor", b.calls[0])                    # the writer sees the Look as a choice
        self.assertEqual(r.pictures[0]["look"], ["Watercolor", "Serene", "Golden hour"])
        self.assertEqual(looks.saved()["last"], ["Watercolor", "Serene", "Golden hour"])
        self.assertEqual([s["action"] for s in r.steps], ["prompt", "look", "picture", "eyes"])   # 👁 M1
        self.assertEqual(args["negative_prompt"], "text, words, letters, writing, caption, subtitles, labels, table, chart, document, "
                         "watermark, signature, logo, username, frame, border, " + looks.NOT_PHOTO)

    def test_look_with_medium_skips_the_style_question(self):
        mcp = PicMCP()
        r, _ = self.make(mcp, "a castle\nLook: Pixel art", ask=True)
        t = threading.Thread(target=r.loop)
        t.start()
        self.assertTrue(wait_for(lambda: r.question is not None))
        self.assertEqual([i["q"] for i in r.question["items"]], ["Shape?"])
        r.answer("Shape? → Wide (screen)")
        t.join(5)
        self.assertEqual(r.state, "done", r.why)
        self.assertIn("pixel art", mcp.args[mcp.calls.index("image_make")]["prompt"])

    def test_look_without_medium_keeps_the_style_choice(self):
        mcp = PicMCP()
        r, _ = self.make(mcp, "a castle\nStyle: Painted / illustrated\nLook: Moonlight")
        r.loop()
        p = mcp.args[mcp.calls.index("image_make")]["prompt"]
        self.assertTrue(p.startswith("a castle. Painted / illustrated."), p)
        self.assertTrue(p.endswith("moonlight."))

    def test_clash_and_limit_notes_recorded(self):
        mcp = PicMCP()
        r, _ = self.make(mcp, "a lake\nLook: Photo · Watercolor · Black & white · Vibrant")
        r.loop()
        st = next(s for s in r.steps if s["action"] == "look")["result"]
        self.assertEqual(st["look"], ["Photo", "Black & white", "Vibrant"])
        self.assertTrue(st["notes"])
        self.assertEqual(st["clash"], ["Black & white + Vibrant"])

    def test_no_look_is_unchanged(self):
        mcp = PicMCP()
        r, _ = self.make(mcp, "a cabin\nStyle: Photo-real")
        r.loop()
        self.assertEqual([s["action"] for s in r.steps], ["prompt", "picture", "eyes"])   # 👁 M1: the look after the picture
        self.assertEqual(r.pictures[0]["look"], [])


# ---------- M2/M3: server routes + page wiring ----------
from pathlib import Path  # noqa: E402

from tests.test_server import Srv  # noqa: E402

HTML = (Path(__file__).resolve().parent.parent / "ailab" / "web" / "index.html").read_text()


class Routes(Srv):
    def test_catalog_save_delete(self):
        code, r, _ = self.req("/api/looks")
        self.assertEqual(code, 200)
        self.assertTrue(r["ok"] and r["tabs"] and r["max_total"] == 8 and r["saved"] == [] and r["last"] == [])
        code, r, _ = self.req("/api/looks/save", {"name": "Dusk oil", "look": ["Oil painting", "Watercolor", "Golden hour"]})
        self.assertEqual(r["saved"], [{"name": "Dusk oil", "look": ["Oil painting", "Golden hour"]}])   # medium limit applied
        code, r, _ = self.req("/api/looks/save", {"name": "", "look": ["Photo"]})
        self.assertFalse(r["ok"])
        code, r, _ = self.req("/api/looks/delete", {"name": "dusk oil"})
        self.assertEqual(r["saved"], [])


class Page(Base):
    def test_page_has_look_line_and_carries_it(self):
        _page()


def _page():
    assert "lookFill(row," in HTML and "function lookPicker(pid)" in HTML and 'id: "aglook"' in HTML
    assert "look.show(on.includes(\"image\") || on.includes(\"video\"))" in HTML   # while 🖼 Image or 🎬 Video is picked (2026-11-25)
    assert "task: look.text(task.value)" in HTML                              # ▶ Start adds the Look line
    assert "const lk = lookFromText(text); if (lk.length) look.set(lk)" in HTML   # Make another / Change it bring it back
    assert HTML.count('.split("\\nLook:")[0]') == 2
    assert HTML.count("`\\nLook: ${last.look.join(LOOK_SEP)}`") == 2
    assert 'dialog", { class: "lookdlg"' in HTML and "/api/looks/save" in HTML and "/api/looks/delete" in HTML
    for limit in ("max === 1 && same.length", "picks at most", "may fight each other"):
        assert limit in HTML, limit


# 🦴 anatomy study (2026-11-25)
def test_study_tab_adult_guard():
    from ailab import looks
    cat = looks.catalog()
    st = next(t for t in cat["tabs"] if t["id"] == "study")
    assert st["max"] == 1 and len(st["items"]) == 19
    assert all("adult" in i["p"] for i in st["items"])
    neg = looks.negative(["Photo", "Feet study"], "text")
    assert "child" in neg and "extra toes" in neg
    assert "child" not in looks.negative(["Photo"], "text")
    assert "photograph" in looks.negative(["Anatomy atlas", "Arms study"], "text")
    head, _ = looks.parts(["Photo", "Face study"])
    assert any("head-and-shoulders" in w for w in head)
    kept, notes = looks.normalize(["Face study", "Feet study"])
    assert kept == ["Face study"] and notes


def test_study_m2_negatives_and_route():
    from types import SimpleNamespace
    from ailab import looks, picture_route
    n = looks.negative(["Photo", "Female figure", "Hips study"], "t")
    assert "ecorche" in n and "mannequin" in n and "full skeleton" not in n
    d = looks.negative(["Anatomy atlas", "Arms study"], "t")
    assert "full skeleton" in d and "skull" in d and "mannequin" not in d
    assert "skull" not in looks.negative(["Anatomy atlas", "Face study"], "t").split("ecorche")[0].split("sketch sheet, ")[-1]
    picture_route._ROWS.update(at=9e18, rows=[{"id": "local/juggernaut-xl-v9"}, {"id": "local/sdxl-base-1.0"}], src=id(None))
    run = SimpleNamespace(cfg={}, lab=SimpleNamespace(mcp=None))
    assert picture_route.plan(run, ["Photo", "Feet study"], "", "venice/lustify-v8", False)["models"] == ["local/juggernaut-xl-v9"]
    assert picture_route.plan(run, ["Anatomy atlas", "Feet study"], "", "venice/lustify-v8", False)["models"] == ["local/juggernaut-xl-v9", "local/sdxl-base-1.0"]
    picture_route._ROWS.update(rows=[])
    assert picture_route.plan(run, ["Photo", "Feet study"], "", "venice/lustify-v8", False)["models"] == []
    picture_route.forget()


def test_study_photo_only_words():
    from ailab import looks
    ph = " ".join(looks.parts(["Photo", "Hips study"])[0])
    at = " ".join(looks.parts(["Anatomy atlas", "Hips study"])[0])
    assert "briefs" in ph and "briefs" not in at

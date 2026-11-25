"""🎭 R1 global cast + 🎲 Design a cast (prompt #2, Scott 2026-11-25): distinct briefs on purpose (validator), redesign
keeps them distinct, the project remembers its cast, reuse pins in the global store, thumbnails only from Hermes's
assets folder, and a whole design run: anchors → 👁 tell-apart (redesign on a miss) → sheets → cast_make each."""
from __future__ import annotations

import base64
import os
from pathlib import Path

from ailab import batch, cast, refs
from tests.test_agent import Base
from tests.test_refs import RefMCP, Refs, png

HTML = (Path(__file__).resolve().parent.parent / "ailab" / "web" / "index.html").read_text()


class CastBase(Refs):
    """Refs's fixtures without re-running Refs's own tests."""


for _n in [n for n in dir(Refs) if n.startswith("test_")]:
    setattr(CastBase, _n, None)


class CastMCP(RefMCP):
    """RefMCP + the Hermes cast tools. `apart` = answers for the tell-apart checks in order (then True)."""
    def __init__(self, apart=None):
        super().__init__(same=True)
        self.apart, self.saved, self.pins = list(apart or []), [], []

    def call(self, tool, args=None):
        args = args or {}
        if tool == "vision_check" and len(args.get("points") or []) == 2 and "mistake" in args["points"][1]:
            self.calls.append(tool)
            self.args.append(args)
            ok = self.apart.pop(0) if self.apart else True
            self._ans = [ok, not ok]
            return {"ok": True, "key": "vis:apart"}
        if tool == "job_wait" and args.get("key") == "vis:apart":
            self.calls.append(tool)
            self.args.append(args)
            return {"state": "done", "finished": True, "result": {"caption": "two people", "answers": [
                {"n": 1, "yes": self._ans[0]}, {"n": 2, "yes": self._ans[1]}]}}
        if tool == "cast_make":
            self.calls.append(tool)
            self.args.append(args)
            cid = f"c-{args['name'].lower()}-000001"
            self.saved.append({**args, "id": cid})
            return {"ok": True, "id": cid, "name": args["name"]}
        if tool == "cast_pin":
            self.calls.append(tool)
            self.pins.append(args)
            return {"ok": True, "id": args["id"], "name": args["id"].split("-")[1].title()}
        return super().call(tool, args)


class Briefs(Base):
    def test_design_is_distinct_for_every_size_and_seed(self):
        for n in (2, 3, 4):
            for seed in range(40):
                bs = cast.design(n, seed)
                self.assertEqual(len(bs), n)
                self.assertEqual(cast.validate(bs), [], (n, seed, bs))
                self.assertTrue(all(b["age"] >= 18 for b in bs))
        self.assertEqual(cast.design(2, 7), cast.design(2, 7), "same seed, same cast")
        self.assertEqual(len(cast.design(9, 1)), cast.MAX_N)

    def test_validator_names_the_problems(self):
        a, b = cast.design(2, 3)
        twin = {**b, "traits": {**b["traits"], "hair_colour": a["traits"]["hair_colour"]}}
        self.assertIn("share hair colour", " ".join(cast.validate([a, twin])))
        close = {**b, "traits": {**a["traits"], "hair_colour": b["traits"]["hair_colour"], "outfit_colour": b["traits"]["outfit_colour"]}}
        self.assertIn("differ on only 2", " ".join(cast.validate([a, close])))
        self.assertIn("adult", " ".join(cast.validate([a, {**b, "age": 16}])))
        self.assertIn("share a name", " ".join(cast.validate([a, {**b, "name": a["name"]}])))
        self.assertTrue(cast.validate([a]))

    def test_redesign_changes_every_trait_and_stays_valid(self):
        bs = cast.design(3, 11)
        nb = cast.redesign(bs, 1, 5)
        self.assertEqual(nb[1]["name"], bs[1]["name"])
        self.assertTrue(all(nb[1]["traits"][ax] != bs[1]["traits"][ax] for ax in cast.AXES))
        self.assertEqual(cast.validate(nb), [])
        self.assertEqual(nb[1]["redesigned"], 1)

    def test_prompt_has_no_text_words_and_says_adult_age(self):
        b = cast.design(2, 1)[0]
        p = cast.picture_prompt(b)
        self.assertIn(f"{b['age']}-year-old", p)
        self.assertIn(b["traits"]["hair_colour"], p)
        self.assertNotIn(b["name"], p, "the name never goes on the art")

    def test_batch_norm_and_price(self):
        n = batch.norm({"cast": {"n": 3}}, ["image"])
        self.assertEqual((n["kind"], n["n"]), ("cast", 3))
        self.assertEqual(batch.norm({"cast": {"n": 99}}, ["image"])["n"], 4)
        self.assertIsNone(batch.norm({"cast": {"n": 2}}, ["text"]))
        self.assertAlmostEqual(batch.price("cast", {}), batch.PICTURE_USD * batch.CAST_PICTURES)


class Store(CastBase):
    def test_choose_survives_and_pull_pins_each(self):
        cast.choose(self.root, "Mara & Jun", ["c-mara-1", "c-jun-2"])
        self.assertEqual(cast.chosen(self.root), {"cast": "Mara & Jun", "ids": ["c-mara-1", "c-jun-2"]})
        m = CastMCP()
        r = cast.pull(m, self.root, "proj-2", "", ["c-mara-000001", "c-jun-000002", "bogus"])
        self.assertTrue(r["ok"])
        self.assertEqual([p["project"] for p in m.pins], ["proj-2", "proj-2"])
        self.assertEqual(cast.chosen(self.root)["ids"], ["c-mara-000001", "c-jun-000002"])
        self.assertFalse(cast.pull(m, self.root, "p", "x", [])["ok"])

    def test_import_refs_copies_and_keeps_originals(self):
        refs.pin(self.root, "pictures/p0.png")
        m = CastMCP()
        r = cast.import_refs(m, self.root, "proj")
        self.assertTrue(r["ok"])
        self.assertEqual(base64.b64decode(m.saved[0]["anchor_b64"]), (self.root / "pictures/p0.png").read_bytes())
        self.assertTrue((self.root / "pictures/p0.png").is_file())
        self.assertGreaterEqual(m.saved[0]["age"], 18)

    def test_thumbnail_only_from_assets(self):
        d = Path(self.tmp.name) / "hd"
        os.environ["HERMES_DATA"] = str(d)
        self.addCleanup(lambda: os.environ.pop("HERMES_DATA", None))
        (d / "assets/c-mara-1/pictures").mkdir(parents=True)
        good = d / "assets/c-mara-1/pictures/anchor.png"
        good.write_bytes(png())
        (d / "settings").mkdir()
        (d / "settings/x.png").write_bytes(png())
        self.assertEqual(cast.picture(str(good))[1], "image/png")
        for bad in (str(d / "settings/x.png"), str(d / "assets/c-mara-1/../../settings/x.png"), str(self.root / "pictures/p0.png"), ""):
            self.assertEqual(cast.picture(bad), (b"", ""), bad)


class DesignRun(CastBase):
    def test_whole_run_redesigns_a_mixed_up_pair_then_saves_both(self):
        self._local_up()
        m = CastMCP(apart=[False, True])          # first look: too alike → redesign person 2 → second look passes
        r = self._run(m, task="Design a cast of 2 people", batch_req={"cast": {"n": 2}})
        r.loop()
        self.assertEqual(r.state, "done", r.why)
        self.assertEqual([s["name"] for s in m.saved], [b["name"] for b in r.batch["briefs"]])
        self.assertTrue(all(len(s["sheet_b64"]) == 5 and s["casts"] == [cast.cast_name(r.batch["briefs"])] for s in m.saved))
        self.assertEqual(r.batch["briefs"][1].get("redesigned"), 1)
        anchors = [it for it in r.batch["items"] if "anchor" in it["variation"]]
        self.assertEqual(len(anchors), 3, "two anchors + one redesign")
        self.assertEqual([c.get("apart") for c in r.batch["apart"]], [False, True])
        makes = [a for t, a in zip(m.calls, m.args) if t == "image_make"]
        self.assertTrue(all("reference_images" not in a for a in makes[:3]), "anchors are words only")
        self.assertEqual(sum(1 for a in makes if a.get("reference_images")), 10, "5 sheet views each, anchor as reference")
        self.assertEqual(cast.chosen(r.root)["ids"], [s["id"] for s in m.saved])
        self.assertIn("Tell-apart: 1/1", r.why)
        v = r.view()["batch"]
        self.assertEqual(v["kind"], "cast")
        self.assertEqual(len(v["saved"]), 2)

    def test_a_pair_that_never_passes_is_reported_not_hidden(self):
        self._local_up()
        m = CastMCP(apart=[False, False, False])
        r = self._run(m, task="Design a cast of 2 people", batch_req={"cast": {"n": 2}})
        r.loop()
        self.assertEqual(r.state, "done", r.why)
        self.assertIn("Still too alike", r.why)
        self.assertEqual(len([c for c in r.batch["apart"] if c.get("apart") is False]), 3)

    def test_no_project_references_leak_into_anchors(self):
        self._local_up()
        refs.pin(self._run(CastMCP()).root, self._copy_pic(self._run(CastMCP()).root))
        m = CastMCP()
        r = self._run(m, task="Design a cast of 2 people", batch_req={"cast": {"n": 2}})
        refs.pin(r.root, self._copy_pic(r.root))
        r.loop()
        makes = [a for t, a in zip(m.calls, m.args) if t == "image_make"]
        self.assertTrue(all("reference_images" not in a for a in makes[:2]))
        pinned = str((r.root / "pictures/ref.png").resolve())
        self.assertTrue(all(pinned not in (a.get("reference_images") or []) for a in makes))


class UI(Base):
    def test_ui_wiring(self):
        for s in ("function castPicker", "♻️ Reuse a cast", "🆕 Make a new one", "/api/cast/choose", "/api/cast/import",
                  "castDesign:", "cast: { n }", "🎭 Global cast"):
            self.assertIn(s, HTML)


class SendSize(Base):
    def test_big_pictures_are_shrunk_under_the_hermes_limit(self):
        import io
        import random
        from PIL import Image
        rnd = random.Random(1)
        im = Image.frombytes("RGB", (1600, 2400), bytes(rnd.getrandbits(8) for _ in range(1600 * 2400 * 3)))
        b = io.BytesIO()
        im.save(b, "PNG")
        raw = b.getvalue()
        self.assertGreater(len(raw), 3_000_000)
        out = cast.small(raw)
        self.assertLess(len(out), len(raw) // 3)
        self.assertEqual(out[:3], b"\xff\xd8\xff", "JPEG")
        w, h = Image.open(io.BytesIO(out)).size
        self.assertEqual(max(w, h), cast.SEND_PX)
        self.assertEqual(cast.small(b"tiny"), b"tiny")
        self.assertEqual(len(cast._fit(["x" * 2_000_000] * 5)), 2, "views that don't fit beside the anchor are dropped")

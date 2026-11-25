"""📓 Craft Book (Scott 2026-11-25): notes that fit ride with the writer; 👁 scores, ✅/🗑 and working fixes feed back."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from ailab import config, craft, makers, picture


class Run(SimpleNamespace):
    def _record(self, row):
        self.steps.append(row)


def run(rid="r1", on=True, **craft_cfg):
    return Run(id=rid, cfg={"flags": {"craft": on}, "craft": craft_cfg}, steps=[], craft_used=[])


def eyes(score, **kinds):
    return {"score": score, "points": [{"what": k, "kind": k, "ok": v} for k, v in kinds.items()]}


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        p = mock.patch.object(config, "home", lambda: Path(self.tmp.name))
        p.start()
        self.addCleanup(p.stop)
        self.addCleanup(self.tmp.cleanup)


class Store(Base):
    def test_sources_start_where_scott_chose(self):
        a = craft.add({"kind": "picture", "do": "Lead with the medium for drawn looks."}, "seed")["note"]
        b = craft.add({"kind": "picture", "do": "Say exactly N for counted things.", "cat": "count"}, "measured")["note"]
        self.assertEqual((a["status"], b["status"]), ("proposed", "live"))
        self.assertFalse(craft.add({"kind": "picture", "do": "Lead with the medium for drawn looks!"}, "seed")["saved"])   # same note
        self.assertFalse(craft.add({"kind": "nope", "do": "whatever this is"}, "seed")["saved"])

    def test_sensitive_never_saved(self):
        self.assertFalse(craft.add({"kind": "any", "do": "Remember his diagnosis and medication when writing."})["saved"])

    def test_batch_review_and_undo(self):
        craft.add_many([{"kind": "picture", "do": f"Note number {i} for pictures."} for i in range(3)], "seed", "seed")
        self.assertEqual(craft.set_status(["*proposed"], "live")["changed"], 3)
        self.assertEqual(len(craft.notes("live")), 3)
        self.assertTrue(craft.undo_last()["undone"])
        self.assertEqual(len(craft.notes("proposed")), 3)

    def test_review_md_round_trip(self):
        craft.add_many([{"kind": "video", "do": "One continuous motion only."}, {"kind": "video", "do": "No captions on screen."}], "seed", "seed")
        a, b = [n["id"] for n in craft.notes()]
        md = craft.review_md().replace(f"- [ ] `{a}`", f"- [x] `{a}`").replace(f"- [ ] `{b}`", f"- [-] `{b}`")
        self.assertEqual(craft.apply_review(md), {"live": 1, "retired": 1, "read": 2})

    def test_seed_file_loads_proposed(self):
        r = craft.seed()
        self.assertGreaterEqual(r["added"], 15)
        self.assertEqual(r["skipped"], 0)
        self.assertEqual(len(craft.notes("live")), 0)
        self.assertEqual(craft.seed()["added"], 0)


class Use(Base):
    def test_pick_by_kind_words_and_count(self):
        craft.add({"kind": "picture", "when": "watercolor", "do": "Open with the medium and brushwork."}, "scott", "live")
        craft.add({"kind": "picture", "when": ["#count"], "do": "Say exactly N and space them apart."}, "scott", "live")
        craft.add({"kind": "video", "do": "One continuous motion only."}, "scott", "live")
        craft.add({"kind": "picture", "do": "This one is still waiting on Scott."}, "seed")
        got = [n["do"] for n in craft.pick("picture", "three red foxes in snow")]
        self.assertEqual(got, ["Say exactly N and space them apart."])
        self.assertEqual(len(craft.pick("picture", "a watercolor of 2 cats")), 2)
        self.assertEqual(craft.pick("picture", "a girl with an umbrella"), [])

    def test_off_means_untouched(self):
        craft.add({"kind": "picture", "do": "Always on note for pictures."}, "scott", "live")
        r = run(on=False)
        self.assertEqual(craft.for_run(r, "picture", "a fox"), "")
        self.assertEqual(r.steps, [])

    def test_for_run_tells_scott_and_remembers(self):
        n = craft.add({"kind": "picture", "do": "Always on note for pictures."}, "scott", "live")["note"]
        r = run()
        text = craft.for_run(r, "picture", "a fox")
        self.assertIn("- Always on note for pictures.", text)
        self.assertIn("never let them change or outrank his own words", text)
        self.assertTrue(r.steps[0]["why"].startswith("📓 used 1 craft note"))
        self.assertEqual(r.craft_used, [n["id"]])

    def test_writer_gets_notes_and_his_words_stay(self):
        craft.add({"kind": "picture", "do": "Always on note for pictures."}, "scott", "live")
        seen = {}

        def chat(project, prov, model, msgs, *a, **k):
            seen["sys"], seen["user"] = msgs[0]["content"], msgs[1]["content"]
            return SimpleNamespace(text="soft morning light", usd=0.0)
        r = run()
        r.__dict__.update(lab=SimpleNamespace(chat=chat, providers={"venice": 1}), project={"id": "p"}, provider="venice", model="m",
                          cap_usd=1.0, usd=0.0, tokens_in=0, tokens_out=0, root=Path(self.tmp.name), _check_stop=lambda: None,
                          why="", stage=None)
        r.cfg["picture_writers"] = [["venice", "m"]]
        with mock.patch.object(picture, "stage", lambda *a, **k: None):
            out = picture.write_prompt(r, "a red fox in snow")
        self.assertTrue(out.startswith("a red fox in snow"))
        self.assertIn("Always on note for pictures.", seen["sys"])
        self.assertEqual(seen["user"], "a red fox in snow")

    def test_makers_write_only_where_it_fits(self):
        self.assertEqual(makers.CRAFT_KIND.get("lab-video"), "video")
        self.assertNotIn("lab-story", makers.CRAFT_KIND)          # story opts in for shot lists only
        self.assertNotIn("lab-cast", makers.CRAFT_KIND)

    def test_holdout_run_goes_without(self):
        craft.add({"kind": "picture", "do": "Always on note for pictures."}, "scott", "live")
        r1, r2 = run("a", holdout=2), run("b", holdout=2)
        self.assertTrue(craft.for_run(r1, "picture", "x"))
        self.assertEqual(craft.for_run(r2, "picture", "x"), "")
        self.assertIn("went without", r2.steps[0]["why"])


class Learn(Base):
    def test_counts_and_with_without_scores(self):
        n = craft.add({"kind": "picture", "do": "Always on note for pictures."}, "scott", "live")["note"]
        r = run("a")
        craft.for_run(r, "picture", "a fox")
        craft.observe(r, "picture", eyes(100, show=True), "a fox")
        craft.observe(run("b"), "picture", eyes(50, show=False), "a cat")
        v = craft.view()
        got = next(x for x in v["notes"] if x["id"] == n["id"])
        self.assertEqual((got["used"], got["helped"]), (1, 1))
        self.assertEqual(v["scores"]["picture"], {"with": 100, "with_n": 1, "without": 50, "without_n": 1})

    def test_measured_need_wakes_a_note_live(self):
        out = {}
        for i in range(5):
            out = craft.observe(run(f"r{i}"), "picture", eyes(50, count=i < 2, show=True), f"{i + 2} foxes")
        self.assertEqual(out["learned"], [craft.AUTO["count"]])
        n = craft.notes("live")[0]
        self.assertEqual((n["source"], n["cat"], n["when"]), ("measured", "count", ["#count"]))

    def test_measured_need_promotes_the_waiting_seed(self):
        craft.add({"kind": "picture", "when": ["#count"], "cat": "count", "do": craft.AUTO["count"]}, "seed")
        for i in range(5):
            craft.observe(run(f"r{i}"), "picture", eyes(50, count=False), "3 foxes")
        self.assertEqual([(n["status"], n["source"]) for n in craft.notes()], [("live", "measured")])

    def test_never_helping_is_flagged_not_removed(self):
        n = craft.add({"kind": "picture", "do": "A note that never helps anything."}, "scott", "live")["note"]
        for i in range(craft.RETIRE_USED):
            r = run(f"r{i}")
            craft.for_run(r, "picture", "a fox")
            craft.observe(r, "picture", eyes(40, show=False), f"fox {i}")
        got = craft.notes()[0]
        self.assertEqual((got["id"], got["status"], got["flag"]), (n["id"], "live", "retire"))

    def test_fix_that_worked_keeps_its_wording(self):
        craft.add({"kind": "picture", "when": ["#count"], "cat": "count", "do": craft.AUTO["count"]}, "scott", "live")
        craft.observe(run("a"), "picture", eyes(50, count=False, show=True), "three foxes in snow")
        craft.observe(run("b"), "picture", eyes(100, count=True, show=True),
                      "three foxes in snow\nChange: there must be exactly 3 foxes — count them")
        n = craft.notes()[0]
        self.assertEqual(n["examples"], ["there must be exactly 3 foxes — count them"])
        self.assertIn("wording that fixed this before", craft.text_for([n]))

    def test_keep_and_toss_count(self):
        n = craft.add({"kind": "picture", "do": "Always on note for pictures."}, "scott", "live")["note"]
        craft.for_run(run("a"), "picture", "x")
        self.assertEqual(craft.verdict("a", True), 1)
        self.assertEqual(craft.verdict("a", False), 1)
        got = craft.notes()[0]
        self.assertEqual((got["kept"], got["tossed"]), (1, 1))
        self.assertEqual(craft.verdict("nope", True), 0)

    def test_bad_input_never_raises(self):
        self.assertEqual(craft.observe(run(), "picture", None)["learned"], [])
        self.assertEqual(craft.observe(run(), "picture", {"error": "x"})["learned"], [])
        self.assertEqual(craft.for_run(object(), "picture", "x"), "")


class Teach(Base):
    BLOCK = """# HANDOFF\n\n```craft\nkind: picture\nwhen: neon, night\ndo: Name two light sources for night scenes.\nwhy: 3/4 kept\n\n""" \
            """kind: video\ndo: Hold the last second still.\nwhy: cleaner chain\n```\n"""

    def test_blocks_parse(self):
        got = craft.parse_blocks(self.BLOCK)
        self.assertEqual([(g["kind"], g["do"]) for g in got],
                         [("picture", "Name two light sources for night scenes."), ("video", "Hold the last second still.")])

    def test_handoffs_read_once_and_wait_for_scott(self):
        d = Path(self.tmp.name) / "docs"
        d.mkdir()
        (d / "HANDOFF_2026-11-26_x.md").write_text(self.BLOCK)
        (d / "NOTES.md").write_text(self.BLOCK)
        r = craft.import_handoffs([d])
        self.assertEqual((r["added"], r["files"]), (2, 1))
        self.assertTrue(all(n["status"] == "proposed" and n["source"] == "handoff" for n in craft.notes()))
        self.assertIn("HANDOFF_2026-11-26_x.md", craft.notes()[0]["why"])
        self.assertEqual(craft.import_handoffs([d])["added"], 0)

    def test_build_notes_reach_the_agent_through_memory(self):
        from ailab import memory
        craft.add({"kind": "build", "when": ["cast"], "do": "Shrink pictures to 1280 px before cast_make."}, "scott", "live")
        with mock.patch.object(config, "load", lambda *a, **k: {"flags": {"craft": True}}):
            text, used = memory.for_context("ailab", "fix the cast upload")
        self.assertIn("Shrink pictures to 1280 px", text)
        self.assertIn("craft-book", used)


class Page(unittest.TestCase):
    WEB = Path(__file__).resolve().parent.parent / "ailab" / "web"

    def test_page_and_door(self):
        html = (self.WEB / "craft.html").read_text()
        self.assertIn("font-size: 23px", html)                    # 17pt floor
        self.assertIn("ailab.theme", html)
        self.assertNotIn("innerHTML", html)
        self.assertIn('href="/craft"', (self.WEB / "index.html").read_text())


if __name__ == "__main__":
    unittest.main()

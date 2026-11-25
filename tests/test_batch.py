"""🎛 Batch create (2026-11-24 Module 3): count + Similar ↔ Wild dial, cost before it runs, grid, ➕ Make more, ⭐ Keep."""
from __future__ import annotations

from ailab import agent, batch, config
from tests.test_agent import Base, Brain
from tests.test_picture import PicMCP

WORDS = "a red fox in the snow"


class Dial(Base):
    def test_levels(self):
        self.assertEqual([batch.level(d) for d in (0, 33, 34, 66, 67, 100)], ["similar"] * 2 + ["middle"] * 2 + ["wild"] * 2)

    def test_similar_keeps_his_words_alone(self):
        self.assertEqual({batch.variation(0, k) for k in range(8)}, {""})
        self.assertEqual(batch.variation(25, 0), "")                    # the first one is always his words as typed
        self.assertTrue(batch.variation(25, 3))                         # a small nudge at the top of Similar

    def test_more_changes_further_right_and_subject_kept(self):
        self.assertLess(batch.variation(40, 2).count(","), batch.variation(60, 2).count(","))
        for d in (40, 60, 70, 100):
            self.assertIn("keep the same main subject", batch.variation(d, 2))
        self.assertEqual(batch.wild_look(60, 2), [])
        self.assertEqual(len(batch.wild_look(70, 2)), 2)                 # drawn style + light
        self.assertEqual(len(batch.wild_look(100, 2)), 3)                # + mood
        self.assertEqual(len({batch.variation(80, k) + str(batch.wild_look(80, k)) for k in range(12)}), 12)

    def test_wild_style_rides_in_a_look_line_with_catalog_names(self):
        from ailab import looks
        t, v, names = batch.picture_task(WORDS, 90, 2)
        self.assertTrue(t.startswith(WORDS + "\nVariation: "))
        self.assertEqual(looks.from_task(t), names)
        kept, notes = looks.normalize(names)
        self.assertEqual(kept, names)                                   # every name is in the catalog
        self.assertNotIn("set in", batch.variation(70, 2))              # below 80: a setting, no scene on top
        self.assertEqual(batch.variation(85, 2).count(","), 1)          # 80+: the scene REPLACES the setting
        t2, v2, n2 = batch.picture_task(WORDS + "\nLook: Watercolor", 90, 2)   # his own Look wins
        self.assertEqual(n2, [])
        self.assertEqual(looks.from_task(t2), ["Watercolor"])
        self.assertIn(", as ", v2)

    def test_docs_keep_the_topic(self):
        v = batch.variation(90, 1, "doc")
        self.assertIn("tone:", v)
        self.assertIn("shape:", v)
        self.assertIn("same topic", v)

    def test_his_words_first_then_variation_before_style_lines(self):
        t = batch.with_variation(f"{WORDS}\nStyle: Photo-real\nShape: Wide (screen)", "a closer view")
        self.assertEqual(t.split("\n"), [WORDS, "Variation: a closer view", "Style: Photo-real", "Shape: Wide (screen)"])
        self.assertEqual(batch.with_variation(WORDS, ""), WORDS)

    def test_norm_and_kind(self):
        self.assertIsNone(batch.norm({"n": 1}, ["image"]))              # 1 = an ordinary run
        self.assertIsNone(batch.norm({"n": 4}, ["website"]))            # pages/apps/games: no batch
        self.assertIsNone(batch.norm({"n": 4}, ["video"]))              # video later
        self.assertEqual(batch.norm({"n": 99, "dial": 300}, ["image"])["n"], 24)
        self.assertEqual(batch.norm({"n": 3, "dial": -5}, ["text"])["kind"], "doc")
        self.assertEqual(batch.norm({"n": 3, "dial": 50}, ["image", "text"])["kind"], "picture")

    def test_estimate_holds_to_the_cap(self):
        cfg = config.load({"daily_cap_usd": 2.0})
        e = batch.estimate("picture", 8, cfg, 0.40)
        self.assertTrue(e["fits"])
        self.assertAlmostEqual(e["est_usd"], 8 * batch.PICTURE_USD)
        e = batch.estimate("picture", 24, cfg, 1.95)
        self.assertFalse(e["fits"])
        self.assertEqual(e["max_n"], 4)


class PictureBatch(Base):
    def run_batch(self, n=3, dial=80, start=0, mcp=None):
        mcp = mcp or PicMCP()
        b = Brain(["detail words, soft light"])
        b.mcp = mcp
        r = agent.Run(b, config.load({"mode": "connected"}), self.project, "openrouter", "m", WORDS, ctypes=["image"],
                      batch={"n": n, "dial": dial, "start": start})
        r.loop()
        return r, mcp

    def test_makes_n_varied_pictures(self):
        r, mcp = self.run_batch(3, 80)
        self.assertEqual(r.state, "done", r.why)
        v = r.view()["batch"]
        self.assertEqual(len(v["items"]), 3)
        self.assertEqual(mcp.calls.count("image_make"), 3)
        prompts = [a["prompt"] for t, a in zip(mcp.calls, mcp.args) if t == "image_make"]
        self.assertTrue(all(p.startswith(WORDS) for p in prompts))     # his words untouched, first
        self.assertEqual(len(set(prompts)), 3)
        self.assertEqual(r.task, WORDS)                                 # the run's task is his words again
        self.assertIn("3 of 3 pictures", r.why)
        self.assertEqual(len(r.view()["made"]), 3)
        self.assertEqual(v["next_start"], 3)

    def test_make_more_continues_the_series(self):
        r, _ = self.run_batch(2, 50, start=2)
        self.assertEqual([i["k"] for i in r.batch["items"]], [2, 3])

    def test_failures_are_counted_not_fatal(self):
        r, _ = self.run_batch(2, 10, mcp=PicMCP(fail="model busy"))
        self.assertEqual(r.state, "failed")
        self.assertEqual(r.batch["failed"], 2)

    def test_stage_says_which_one(self):
        r, _ = self.run_batch(2, 10)
        r.state = "running"
        r.stage = {"icon": "🎨", "text": "Making", "at": __import__("time").time()}
        r.batch["now"] = 1
        self.assertTrue(r.view()["stage"]["text"].startswith("🎛 2 of 2 · "))


class DocBatch(Base):
    def test_writes_n_docs(self):
        b = Brain(["# Tips\n\nKeep the fire small and dry wood close."])
        r = agent.Run(b, config.load({"mode": "standalone"}), self.project, "openrouter", "m", "camping tips for winter",
                      ctypes=["text"], batch={"n": 3, "dial": 90})
        r.loop()
        self.assertEqual(r.state, "done", r.why)
        paths = [i["path"] for i in r.batch["items"]]
        self.assertEqual(len(paths), 3)
        self.assertTrue(all(p.startswith("docs/") and p.endswith(".md") for p in paths))
        self.assertTrue((r.root / paths[0]).read_text().startswith("# Tips"))
        self.assertIn("Variation: tone:", b.calls[1])
        self.assertEqual({m["kind"] for m in r.view()["made"]}, {"doc"})

    def test_refusal_is_not_saved(self):
        b = Brain(["Sorry, I can't help with that."])
        r = agent.Run(b, config.load({"mode": "standalone"}), self.project, "openrouter", "m", "x", ctypes=["text"],
                      batch={"n": 2, "dial": 0})
        r.loop()
        self.assertEqual(r.state, "failed")
        self.assertEqual(list((r.root / "docs").glob("*.md")) if (r.root / "docs").exists() else [], [])


class Keep(Base):
    def test_keep_and_unkeep(self):
        r = agent.Run(Brain(["x"]), config.load({}), self.project, "openrouter", "m", "x", ctypes=["text"])
        (r.root / "docs").mkdir(parents=True, exist_ok=True)
        (r.root / "docs" / "a.md").write_text("a")
        self.assertEqual(batch.set_kept(r.root, "docs/a.md", True), ["docs/a.md"])
        self.assertEqual(batch.kept(r.root), ["docs/a.md"])
        self.assertEqual(batch.set_kept(r.root, "docs/a.md", False), [])
        with self.assertRaises(ValueError):
            batch.set_kept(r.root, "../etc/passwd", True)


class Spent:
    def __init__(self, usd):
        self.usd = usd

    def spent_today(self):
        return self.usd


class ServerBatch(Base):
    def app(self, spent=0.0):
        from ailab import server
        b = Brain(["# Doc\n\nSome words for the doc here."])
        b.mcp, b.spend = None, Spent(spent)
        a = server.App(config.load({"flags": {"agent": True}, "daily_cap_usd": 2.0}), lab=b)
        return a

    def test_estimate_and_cap_refusal_before_anything_runs(self):
        a = self.app(spent=1.95)
        code, e = a.batch_estimate({"ctypes": ["image"], "n": 8})
        self.assertTrue(e["ok"])
        self.assertFalse(e["fits"])
        code, r = a.agent_start({"project": "scratch", "provider": "openrouter", "model": "m", "task": WORDS,
                                 "ctypes": ["image"], "batch": {"n": 8, "dial": 50}})
        self.assertFalse(r["ok"])
        self.assertEqual(r["code"], "cap")
        self.assertIn("4 or fewer", r["message"])
        code, e = a.batch_estimate({"ctypes": ["website"], "n": 8})
        self.assertEqual(e["kind"], "")

    def test_make_more_carries_earlier_and_continues(self):
        import time
        a = self.app()
        code, r = a.agent_start({"project": "scratch", "provider": "openrouter", "model": "m", "task": "winter tips",
                                 "ctypes": ["text"], "batch": {"n": 2, "dial": 60}})
        self.assertTrue(r["ok"], r)
        first = a.agents.get(r["run"]["id"])
        for _ in range(100):
            if first.state != "running":
                break
            time.sleep(0.05)
        self.assertEqual(first.state, "done", first.why)
        code, r2 = a.agent_start({"project": "scratch", "provider": "openrouter", "model": "m", "task": "winter tips",
                                  "ctypes": ["text"], "batch": {"n": 2, "dial": 60, "from_run": first.id}})
        self.assertTrue(r2["ok"], r2)
        v = r2["run"]["batch"]
        self.assertEqual(v["start"], 2)
        self.assertEqual(len(v["earlier"]), 2)
        second = a.agents.get(r2["run"]["id"])
        for _ in range(100):
            if second.state != "running":
                break
            time.sleep(0.05)
        self.assertEqual([i["k"] for i in second.batch["items"]], [2, 3])

    def test_hermes_down_spend_unknown_still_estimates(self):
        a = self.app()
        a.lab.spend = None                                   # spent_today() fails → today unknown
        code, e = a.batch_estimate({"ctypes": ["image"], "n": 2})
        self.assertTrue(e["ok"] and e["fits"])

"""📖 M3 Story (eyes+story+rip, Scott 2026-11-25): bible survives a restart, shot list ↔ stills mapping (cast anchors as
references), a low $0 still is remade once, continuity flag on a planted contradiction, the film is joined, narration
off says why, words-only writes prose, a restarted chapter skips finished shots."""
from __future__ import annotations

import json
import shutil
import unittest
from pathlib import Path

from ailab import agent, batch, config, story
from tests.test_agent import ChatResult
from ailab.mcp_client import HermesRefused
from tests.test_agent import Base
from tests.test_refs import RefMCP, png

HTML = (Path(__file__).resolve().parent.parent / "ailab" / "web" / "index.html").read_text()
SHOTS = {"outline": "Mara and Jun race to the lighthouse.", "shots": [
    {"who": ["mara"], "where": "a stormy pier", "action": "Mara sprints through the rain", "camera": "wide, slow push-in", "seconds": 3, "line": "She ran."},
    {"who": ["Jun", "Mara"], "where": "the lighthouse door", "action": "Jun grabs Mara's hand", "camera": "close-up", "seconds": 3, "line": ""},
    {"who": ["Jun"], "where": "the lamp room", "action": "Jun lights the lamp", "camera": "low angle", "seconds": 40, "line": "Light."}]}


class StoryBrain:
    def __init__(self, flags=None, shots=None):
        self.flags, self.shots, self.calls = list(flags or []), shots or SHOTS, []

    def chat(self, project, prov, model, msgs, max_tokens=1024, cap_usd=None, task=""):
        sys = msgs[0]["content"]
        self.calls.append(sys[:40])
        if "check a new chapter plan" in sys:
            t = json.dumps(self.flags.pop(0) if self.flags else [])
        elif "story bible" in sys:
            t = json.dumps({"title": "Lighthouse Run", "tone": "tense", "people": [{"name": "Mara", "who": "copper hair"},
                                                                                   {"name": "Jun", "who": "black hair"}],
                            "places": ["the pier"], "rules": ["storms every night"]})
        elif "You plan a" in sys:
            t = "Here you go:\n```json\n" + json.dumps(self.shots) + "\n```"
        elif "check a new chapter plan" in sys:
            t = json.dumps(self.flags.pop(0) if self.flags else [])
        elif "CHANGED" in sys:
            t = '["Jun\'s left arm is broken", "the lamp is lit"]'
        elif "fiction prose" in sys:
            t = "The storm came in low over the pier."
        else:
            t = "dramatic rain, soft rim light."
        return ChatResult(t, prov, model, 10, 5, 0.0, True)


class StoryMCP(RefMCP):
    def __init__(self, scores=None, voice=True, **kw):
        super().__init__(**kw)
        self.scores, self.voice = list(scores or []), voice

    def call(self, tool, args=None):
        args = args or {}
        if tool == "cast_get":
            self.calls.append(tool)
            self.args.append(args)
            name = args["id"].split("-")[1].title()
            p = Path(self.anchor_dir) / f"{name}.png"
            p.write_bytes(png())
            return {"id": args["id"], "name": name, "brief": f"{name}: tall adult", "anchor_path": str(p)}
        if tool == "narrate":
            self.calls.append(tool)
            if not self.voice:
                raise HermesRefused("not_enabled", "The narrator voice didn't speak: natural voice is not running on gandalf", "On gandalf: bash install_tts_on_gandalf.sh")
            import base64
            return {"b64": base64.b64encode(_wav()).decode()}
        if tool == "vision_check" and self.scores:
            self.same = self.scores.pop(0)
        return super().call(tool, args)


def _wav() -> bytes:
    import io
    import wave
    b = io.BytesIO()
    with wave.open(b, "wb") as w:
        w.setnchannels(1), w.setsampwidth(2), w.setframerate(24000), w.writeframes(b"\0\0" * 24000)
    return b.getvalue()


class Story(Base):
    def setUp(self):
        super().setUp()
        self.anchors = Path(self.tmp.name) / "assets"
        self.anchors.mkdir()
        from ailab import picture_route
        orig = (picture_route.ready, picture_route.plan)
        picture_route.ready = lambda run: {"local/flux2-klein-4b", "local/juggernaut-xl-v9"}
        picture_route.plan = lambda run, look, style, vm, forced: {"kind": "photo", "first": "local", "models": ["local/juggernaut-xl-v9"]}
        self.addCleanup(lambda: (setattr(picture_route, "ready", orig[0]), setattr(picture_route, "plan", orig[1])))

    def _run(self, mcp, brain=None, req=None, task="a storm race to the lighthouse"):
        b = brain or StoryBrain()
        b.mcp = mcp
        mcp.anchor_dir = str(self.anchors)
        return agent.Run(b, config.load({"mode": "connected"}), self.project, "openrouter", "m", task, ctypes=["image"],
                         batch={"story": req or {"form": "short", "clips": "free", "narrate": True}})

    def _cast(self, root):
        from ailab import cast
        cast.choose(root, "Mara & Jun", ["c-mara-000001", "c-jun-000002"])

    # ---------- pure pieces
    def test_norm_and_batch(self):
        self.assertEqual(story.norm({"form": "bogus"})["form"], "short")
        self.assertEqual(story.norm({"form": "words"})["clips"], "none")
        b = batch.norm({"story": {"form": "long"}}, ["image"])
        self.assertEqual((b["kind"], b["n"]), ("story", story.LONG_SHOTS))
        self.assertIsNone(batch.norm({"story": {}}, ["website"]))

    def test_shots_clean_clamp_and_short_total(self):
        s = story.clean_shots(SHOTS["shots"] + [{"action": ""}, "junk"], ["Mara", "Jun"], "short")
        self.assertEqual(len(s), 3)
        self.assertEqual(s[0]["who"], ["Mara"], "names matched to the cast's spelling")
        self.assertTrue(all(story.SHOT_MIN_S <= x["seconds"] <= story.SHOT_MAX_S for x in s))
        tot = sum(x["seconds"] for x in s)
        self.assertGreaterEqual(tot, story.SHORT_MIN_S - 3)
        self.assertEqual(story._json("no json here", list), [])
        self.assertEqual(story._json('x {"a": "b}"} y', dict), {"a": "b}"})

    def test_bible_survives_restart_and_edits_are_cleaned(self):
        root = Path(self.tmp.name) / "p"
        root.mkdir()
        story.save_bible(root, {"title": "T", "people": [{"name": "Mara", "who": "x"}, {"who": "no name"}], "facts": [{"ch": 1, "fact": "f"}]})
        b = story.bible(root)
        self.assertEqual((b["title"], len(b["people"]), b["facts"][0]["fact"]), ("T", 1, "f"))

    # ---------- the run
    def test_short_story_end_to_end(self):
        m = StoryMCP()
        r = self._run(m)
        self._cast(r.root)
        r.loop()
        self.assertEqual(r.state, "done", r.why)
        ch = story.chapter(r.root, 1)
        self.assertEqual(len(ch["shots"]), 3)
        self.assertTrue(all(s.get("still") and (r.root / s["still"]).is_file() for s in ch["shots"]), "every shot has its still")
        self.assertTrue(all(s.get("clip", "").endswith(".mp4") for s in ch["shots"]))
        makes = [a for t, a in zip(m.calls, m.args) if t == "image_make"]
        self.assertEqual(len(makes), 3)
        self.assertEqual(len(makes[1]["reference_images"]), 2, "shot 2 has Jun and Mara → both anchors")
        self.assertIn("Mara.png", makes[0]["reference_images"][0])
        self.assertIn("Mara (tall adult)", makes[0]["prompt"])
        self.assertTrue(all("(" not in q for q in m.points), "👁 points carry no bracketed looks")
        self.assertTrue(ch["film"] and (r.root / ch["film"]).is_file() and ch["voice"])
        self.assertTrue(r.videos and r.videos[-1]["path"] == ch["film"])
        self.assertEqual(len(story.bible(r.root)["facts"]), 2, "what changed went into the bible")
        self.assertIn("Spend: $0.000", r.why)
        self.assertEqual(r.view()["batch"]["kind"], "story")

    def test_low_free_still_is_remade_once(self):
        m = StoryMCP(scores=[False, True, True, True])
        r = self._run(m, req={"form": "short", "clips": "none", "narrate": False})
        r.loop()
        self.assertEqual(r.state, "done", r.why)
        makes = [a for t, a in zip(m.calls, m.args) if t == "image_make"]
        self.assertEqual(len(makes), 4, "shot 1 remade once after a low score")
        self.assertTrue(any("remaking it once" in (s.get("why") or "") for s in r.steps))

    def test_narration_off_says_why_and_film_is_silent(self):
        r = self._run(StoryMCP(voice=False))
        r.loop()
        self.assertEqual(r.state, "done", r.why)
        self.assertTrue(any("narration skipped" in (s.get("why") or "") and "install" in s["why"] for s in r.steps))
        self.assertIn("(no voice)", r.why)

    def test_continuity_flag_on_planted_contradiction(self):
        m = StoryMCP()
        r = self._run(m, brain=StoryBrain(flags=[["Jun uses his broken left arm"]]), req={"form": "long", "clips": "none", "narrate": False})
        story.save_bible(r.root, {"title": "Lighthouse Run", "people": [{"name": "Jun", "who": "x"}], "facts": [{"ch": 1, "fact": "Jun's left arm is broken"}]})
        story.save_chapter(r.root, 1, {"form": "long", "shots": [], "done": True})
        r.ask_first = True
        import threading
        t = threading.Thread(target=r.loop)
        t.start()
        for _ in range(200):
            if r.question:
                break
            t.join(0.05)
        self.assertTrue(r.question and "broken left arm" in r.question["text"], r.question)
        r.answer(story.FIX_BIBLE)
        t.join(30)
        self.assertEqual(r.state, "done", r.why)
        self.assertEqual(r.batch["chapter"], 2)
        self.assertTrue(any("Changed in chapter 2" in f["fact"] for f in story.bible(r.root)["facts"]))

    def test_restart_skips_finished_shots(self):
        m = StoryMCP()
        r = self._run(m, req={"form": "short", "clips": "none", "narrate": False})
        r.loop()
        ch = story.chapter(r.root, 1)
        ch["shots"][2].pop("still")
        ch["done"] = False
        story.save_chapter(r.root, 1, ch)
        m2 = StoryMCP()
        r2 = self._run(m2, req={"form": "short", "clips": "none", "narrate": False})
        r2.loop()
        self.assertEqual(r2.batch["chapter"], 1, "the unfinished chapter is carried on")
        self.assertEqual(sum(1 for t in m2.calls if t == "image_make"), 1, "only the missing shot is made")

    def test_run_stays_running_between_shots(self):
        """Live 2026-11-25: a Lab restart between sheet pictures restored the cast run as "done" with nothing saved."""
        from ailab import picture as P
        seen, orig = [], P.run

        def spy(run):
            orig(run)
            seen.append(run.state)
        P.run = spy
        self.addCleanup(lambda: setattr(P, "run", orig))
        from ailab import story as S
        states = []
        orig_save = S.save_chapter
        S.save_chapter = lambda root, n, d: (states.append(r.state), orig_save(root, n, d))
        self.addCleanup(lambda: setattr(S, "save_chapter", orig_save))
        r = self._run(StoryMCP(), req={"form": "short", "clips": "none", "narrate": False})
        r.loop()
        self.assertEqual(r.state, "done", r.why)
        self.assertIn("done", seen)
        self.assertNotIn("done", states[:-1], "never saved as done mid-chapter")

    def test_words_only_writes_prose(self):
        r = self._run(StoryMCP(), req={"form": "words"})
        r.loop()
        self.assertEqual(r.state, "done", r.why)
        ch = story.chapter(r.root, 1)
        self.assertTrue(ch["prose"].startswith("docs/story-lighthouse-run-ch1"))
        self.assertIn("storm came in", (r.root / ch["prose"]).read_text())

    def test_page_has_story_card(self):
        for s in ("storyBox(", "/api/story", "{ story: opts }", "🔗", "📚 Story bible"):
            self.assertIn(s, HTML, s)


if __name__ == "__main__":
    unittest.main()

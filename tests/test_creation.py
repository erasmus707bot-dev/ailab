"""🧩 Creation type chips (2026-11-24): types file, ⭐ guess, agent brief, robot mode, ship targets, hand-offs, routes."""
from __future__ import annotations

import json

from ailab import agent, config, creation, robotcheck
from tests.test_agent import AgentOn, Base, Brain, act
from tests.test_workflow import DONE, OK, W, wait_for


class TypesFile(Base):
    def test_starting_types(self):
        ids = [t["id"] for t in creation.all_types()]
        self.assertEqual(ids, ["website", "android", "windows", "linux", "game", "text", "edit", "image", "video"])
        for t in creation.all_types():
            self.assertTrue(t["icon"] and t["label"] and t["use"] and t["robot"] in ("play", "page", "none"))

    def test_guess_follows_the_words(self):
        g = creation.guess
        self.assertEqual(g("make a tetris game for my android phone")[:2], ["game", "android"])
        self.assertEqual(g("a landing page website with a logo"), ["website", "image"])
        self.assertEqual(g("write a cover letter"), ["text"])
        self.assertEqual(g("Sitemap"), [])                                  # whole words only ("site" ≠ "sitemap")
        self.assertEqual(g(""), [])

    def test_robot_mode_takes_the_strongest(self):
        self.assertEqual(creation.robot_mode([]), "play")                   # no chips = the test before chips existed
        self.assertEqual(creation.robot_mode(["text"]), "none")
        self.assertEqual(creation.robot_mode(["website"]), "page")
        self.assertEqual(creation.robot_mode(["website", "game"]), "play")
        self.assertEqual(creation.robot_mode(["image", "website"]), "page")

    def test_ship_and_handoffs(self):
        self.assertEqual(creation.ship_targets(["android", "windows", "android"]), ["android", "windows"])
        self.assertEqual(creation.ship_targets(["website"]), [])
        h = creation.handoffs(["image", "video", "text"])
        self.assertEqual([(x["path"], x["file"]) for x in h], [("/models", "image_brief.md"), ("/media", "video_brief.md")])

    def test_unknown_ids_dropped(self):
        self.assertEqual([t["id"] for t in creation.pick(["game", "nope", "game", 3])], ["game"])

    def test_brief_names_types_and_questions_only_when_asking(self):
        b = creation.brief(["website", "image"], ask_first=True)
        self.assertIn("🌐 Website + 🖼 Image", b)
        self.assertIn("image_make", b)
        self.assertIn("Questions worth asking", b)
        self.assertNotIn("Questions worth asking", creation.brief(["website"], ask_first=False))
        self.assertEqual(creation.brief([]), "")

    def test_extra_types_file_adds_replaces_hides(self):
        (config.home() / "creation_types.json").write_text(json.dumps([
            {"id": "music", "icon": "🎵", "label": "Music", "words": ["song"], "robot": "none"},
            {"id": "text", "label": "Words"}, {"id": "video", "off": True}]))
        try:
            by = {t["id"]: t for t in creation.all_types()}
            self.assertIn("music", by)
            self.assertNotIn("video", by)
            self.assertEqual((by["text"]["label"], by["text"]["icon"]), ("Words", "📝"))
            self.assertEqual(creation.guess("a song"), ["music"])
        finally:
            (config.home() / "creation_types.json").unlink()

    def test_bad_extra_file_is_ignored(self):
        (config.home() / "creation_types.json").write_text("{nope")
        try:
            self.assertEqual(len(creation.all_types()), 9)
        finally:
            (config.home() / "creation_types.json").unlink()


class AgentUsesTypes(Base):
    def run_with(self, ctypes, replies, robot=None, ask_first=False):
        seen = []

        def rb(run):
            seen.append(run.id)
            return robot or {"level": "green", "why": []}
        r = agent.Run(Brain(replies), config.load({"mode": "standalone"}), self.project, "openrouter", "m", "t",
                      selftest=rb, ctypes=ctypes, ask_first=ask_first)
        return r, seen

    def test_system_prompt_gets_the_brief(self):
        seen = []
        b = Brain([DONE])
        orig = b.chat
        b.chat = lambda project, prov, model, msgs, *a, **k: (seen.append(msgs[0]["content"]), orig(project, prov, model, msgs, *a, **k))[1]
        r = agent.Run(b, config.load({"mode": "standalone"}), self.project, "openrouter", "m", "t", ctypes=["game"])
        r.loop()
        self.assertIn("🎮 Game", seen[0])
        self.assertIn("start button", seen[0])

    def test_text_run_needs_no_robot_and_is_done(self):
        w = act(action="write", path="letter.md", content="Hi", why="w")
        r, seen = self.run_with(["text"], [w, OK, DONE])
        r.loop()
        self.assertEqual((r.state, seen), ("done", []))

    def test_without_chips_a_non_page_file_is_still_unproven(self):    # behaviour before chips is unchanged
        w = act(action="write", path="letter.md", content="Hi", why="w")
        r, seen = self.run_with([], [w, OK, DONE])
        r.loop()
        self.assertEqual(r.state, "unproven")

    def test_view_carries_types_ship_handoffs(self):
        r, _ = self.run_with(["android", "image"], [W, OK, DONE])
        r.loop()
        v = r.view()
        self.assertEqual((v["ctypes"], v["ship"], v["robot_mode"]), (["android", "image"], ["android"], "page"))
        self.assertEqual(v["handoffs"][0]["name"], "Image Studio")

    def test_types_survive_a_restart(self):
        r, _ = self.run_with(["windows"], [W, OK, DONE])
        r.loop()
        back = agent.Run.restore(r.lab, r.cfg, r.state_file())
        self.assertEqual(back.view()["ship"], ["windows"])


class PageRobot(Base):
    def test_still_page_is_fine_but_still_game_is_yellow(self):
        v = {"status": 200, "errors": [], "button": "Start", "clicked": True, "moved": False}
        self.assertEqual(robotcheck.judge_play(v, "page")["level"], "green")
        self.assertEqual(robotcheck.judge_play(v, "play")["level"], "yellow")
        self.assertEqual(robotcheck.judge_play(dict(v, errors=["boom"]), "page")["level"], "red")
        self.assertEqual(robotcheck.play("http://x/", driver=lambda u, s, c: v, mode="page")["level"], "green")


class Routes(AgentOn):
    flags = {"agent": True}

    def test_types_route_and_start_with_chips(self):
        code, r, _ = self.req("/api/creation_types")
        self.assertEqual(code, 200)
        self.assertEqual(len(r["types"]), 9)
        self.assertIn("words", r["types"][0])
        self.lab.chat = Brain([act(action="done", summary="ok")]).chat
        code, r, _ = self.req("/api/agent/start", {"project": "scratch", "provider": "ollama", "model": "m", "task": "a site",
                                                   "ctypes": ["website", "bogus"]})
        self.assertEqual(code, 200, r)
        self.assertEqual(r["run"]["ctypes"], ["website"])
        rid = r["run"]["id"]
        self.assertTrue(wait_for(lambda: self.req(f"/api/agent/run?id={rid}")[1]["run"]["state"] == "done"))

    def test_start_without_chips_still_works(self):
        self.lab.chat = Brain([act(action="done", summary="ok")]).chat
        code, r, _ = self.req("/api/agent/start", {"project": "scratch", "provider": "ollama", "model": "m", "task": "x", "ctypes": "nope"})
        self.assertEqual((code, r["run"]["ctypes"]), (200, []))

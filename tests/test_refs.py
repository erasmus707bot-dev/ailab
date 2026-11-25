"""🎭 M2 characters + references (prompt #1, Scott 2026-11-25): 📌 cast strip (1–4 per project), references ride
along to image_make on reference-capable models only, a refused route falls back to words, character sheet = 5 views
with the source as the reference, 👁 same-face check names drift."""
from __future__ import annotations

import base64
import io
from pathlib import Path
from types import SimpleNamespace

from PIL import Image

from ailab import agent, batch, config, picture, picture_route, refs
from ailab.mcp_client import HermesRefused
from tests.test_agent import Base, Brain

HTML = (Path(__file__).resolve().parent.parent / "ailab" / "web" / "index.html").read_text()


def png(color=(200, 50, 50)) -> bytes:
    b = io.BytesIO()
    Image.new("RGB", (64, 96), color).save(b, "PNG")
    return b.getvalue()


class RefMCP:
    """image_make records args; `refuse_refs` refuses any call that carries reference_images; vision answers `same`."""
    def __init__(self, refuse_refs=False, same=True):
        self.calls, self.args, self.refuse_refs, self.same = [], [], refuse_refs, same

    def call(self, tool, args=None):
        args = args or {}
        self.calls.append(tool)
        self.args.append(args)
        if tool == "image_make":
            if self.refuse_refs and args.get("reference_images"):
                raise HermesRefused("not_enabled", "Reference pictures on local are off until the asset-library identity probe passes.", "Run the probe.")
            return {"ok": True, "key": "img:1", "model": args.get("model", "x"), "est_usd": 0.0}
        if tool == "vision_check":
            self.points = args["points"]
            return {"ok": True, "key": "vis:1", "model": "qwen3.5:4b"}
        if tool == "job_wait":
            if args.get("key") == "vis:1":
                return {"state": "done", "finished": True, "result": {"caption": "a person", "answers": [
                    {"n": i + 1, "q": q, "yes": self.same} for i, q in enumerate(self.points)]}}
            return {"state": "done", "finished": True, "result": {"b64": base64.b64encode(png()).decode(), "media_type": "image/png",
                                                                  "model": "local/flux2-klein-4b", "usd": 0.0}}
        return {"ok": True}


class Refs(Base):
    def setUp(self):
        super().setUp()
        self.root = Path(self.tmp.name) / "proj"
        (self.root / "pictures").mkdir(parents=True)
        for i in range(5):
            (self.root / f"pictures/p{i}.png").write_bytes(png())
        (self.root / "notes.md").write_text("x")

    def test_pin_unpin_max_and_only_pictures(self):
        for i in range(4):
            self.assertTrue(refs.pin(self.root, f"pictures/p{i}.png")["ok"])
        self.assertTrue(refs.pin(self.root, "pictures/p0.png")["ok"], "pinning twice is fine")
        self.assertFalse(refs.pin(self.root, "pictures/p4.png")["ok"], "5th refused")
        self.assertFalse(refs.pin(self.root, "notes.md")["ok"])
        self.assertFalse(refs.pin(self.root, "../outside.png")["ok"])
        self.assertEqual(refs.unpin(self.root, "pictures/p1.png")["refs"], ["pictures/p0.png", "pictures/p2.png", "pictures/p3.png"])
        (self.root / "pictures/p2.png").unlink()
        self.assertEqual(refs.get(self.root), ["pictures/p0.png", "pictures/p3.png"], "a deleted picture drops off")

    def test_queue_puts_ref_models_first_only_when_allowed(self):
        self.assertEqual(refs.queue(["local/juggernaut-xl-v9", "venice/lustify"], True, True),
                         ["local/flux2-klein-4b", "venice/qwen-edit-uncensored", "local/juggernaut-xl-v9", "venice/lustify"])
        self.assertEqual(refs.queue(["local/juggernaut-xl-v9"], True, False), ["local/flux2-klein-4b", "local/juggernaut-xl-v9"])
        self.assertEqual(refs.queue(["venice/lustify"], False, False), ["venice/lustify"])

    def _run(self, mcp, task="a red-haired woman in a garden", batch_req=None):
        b = Brain(["A red-haired woman standing in a garden, soft light."] * 10)
        b.mcp = mcp
        r = agent.Run(b, config.load({"mode": "connected"}), self.project, "openrouter", "m", task, ctypes=["image"], batch=batch_req)
        return r

    def _local_up(self):
        orig = (picture_route.ready, picture_route.plan)
        picture_route.ready = lambda run: {"local/flux2-klein-4b", "local/juggernaut-xl-v9"}
        picture_route.plan = lambda run, look, style, vm, forced: {"kind": "photo", "first": "local", "models": ["local/juggernaut-xl-v9"]}
        self.addCleanup(lambda: (setattr(picture_route, "ready", orig[0]), setattr(picture_route, "plan", orig[1])))

    def test_picture_run_sends_references_on_flux2(self):
        self._local_up()
        mcp = RefMCP()
        r = self._run(mcp)
        refs.pin(r.root, self._copy_pic(r.root))
        r.loop()
        self.assertEqual(r.state, "done", r.why)
        a = mcp.args[mcp.calls.index("image_make")]
        self.assertEqual(a["model"], "local/flux2-klein-4b")
        self.assertEqual(len(a["reference_images"]), 1)
        self.assertTrue(Path(a["reference_images"][0]).is_absolute())
        self.assertIn("refs", [s["action"] for s in r.steps])

    def _copy_pic(self, root) -> str:
        (Path(root) / "pictures").mkdir(parents=True, exist_ok=True)
        (Path(root) / "pictures/ref.png").write_bytes(png())
        return "pictures/ref.png"

    def test_refused_references_fall_back_to_words_on_same_model(self):
        self._local_up()
        mcp = RefMCP(refuse_refs=True)
        r = self._run(mcp)
        refs.pin(r.root, self._copy_pic(r.root))
        r.loop()
        # 2026-11-25: with a 📌 reference in play nothing is made without it — the run stops and says why
        makes = [a for t, a in zip(mcp.calls, mcp.args) if t == "image_make"]
        self.assertEqual([m["model"] for m in makes], ["local/flux2-klein-4b"])
        self.assertEqual(r.state, "failed")
        self.assertIn("Nothing made", r.why)
        self.assertIn("Run the probe.", r.why)
        self.assertTrue(any("references not used" in s["why"] for s in r.steps))

    def test_no_ref_model_means_words_only_and_says_so(self):
        mcp = RefMCP()
        r = self._run(mcp)
        refs.pin(r.root, self._copy_pic(r.root))
        orig = picture_route.plan
        picture_route.plan = lambda run, look, style, vm, forced: {"kind": "photo", "first": "venice", "models": ["openai/gpt-image"]}
        self.addCleanup(lambda: setattr(picture_route, "plan", orig))
        r.loop()
        self.assertTrue(all("reference_images" not in a for a in mcp.args))
        self.assertTrue(any("no picture model here can use reference" in s["why"] for s in r.steps))

    def test_sheet_batch_norm_and_tasks(self):
        n = batch.norm({"n": 2, "sheet": "pictures/p0.png"}, ["image"])
        self.assertEqual((n["n"], n["dial"], n["sheet"]), (5, 0, "pictures/p0.png"))
        self.assertIsNone(batch.norm({"n": 2, "sheet": "x.png"}, ["text"]))
        t, v = refs.sheet_task("Mara the knight", 1)
        self.assertTrue(t.startswith("Mara the knight, the same character"))
        self.assertEqual(v, "side view in profile")
        t, _ = refs.sheet_task("Character sheet of the person in this picture\nLook: Photo", 4, "a girl with a red umbrella", "Anime · Serene")
        self.assertTrue(t.startswith("a girl with a red umbrella, the same character as in the reference picture"))
        self.assertIn("same art style", t)
        self.assertTrue(t.endswith("\nLook: Anime · Serene") and "Look: Photo" not in t)

    def test_caption_becomes_who_without_the_scene(self):
        c = ("A single anime-style girl with dark hair stands under a red umbrella in a rain-soaked bus shelter at night. "
             "She wears a white long-sleeve top and a short black skirt, facing slightly left. The scene is lit by blue light.")
        self.assertEqual(refs.from_caption(c), "a single anime-style girl with dark hair, wearing a white long-sleeve top and a short black skirt, facing slightly left")
        self.assertEqual(refs.from_caption("The image shows a red fox sitting in snow."), "a red fox")
        self.assertEqual(refs.from_caption(""), "")

    def test_describe_prefers_his_own_kept_words(self):
        from ailab import shelf
        r = self._run(RefMCP())
        rel = self._copy_pic(r.root)
        shelf.keep(r.root, "k1", "a girl with a red umbrella at a rainy bus stop\nLook: Anime · Serene", [{"path": rel}])
        self.assertEqual(refs.describe(r, rel), ("a girl with a red umbrella at a rainy bus stop", "Anime · Serene"))
        self.assertNotIn("vision_check", r.lab.mcp.calls if hasattr(r.lab.mcp, "calls") else [])

    def test_sheet_run_uses_source_as_reference_and_checks_same_face(self):
        self._local_up()
        mcp = RefMCP(same=False)
        r = self._run(mcp, task="Character sheet of the person in this picture",
                      batch_req={"n": 5, "sheet": "pictures/ref.png"})
        self._copy_pic(r.root)
        refs.pin(r.root, "pictures/ref.png")
        r.loop()
        makes = [a for t, a in zip(mcp.calls, mcp.args) if t == "image_make"]
        self.assertEqual(len(makes), 5)
        self.assertTrue(all(a["reference_images"] == [str((r.root / "pictures/ref.png").resolve())] for a in makes))
        self.assertEqual(mcp.calls.count("vision_check"), 6)                     # 1 describe + 5 same-face looks
        self.assertTrue(any(s["why"].startswith("🎭 the sheet keeps:") for s in r.steps))
        last = [s for s in r.steps if s["action"] == "eyes"][-1]
        self.assertIn("0 of 5 checked views match", last["why"])
        self.assertIn("drifted", last["why"])
        self.assertFalse(r.view()["batch"]["items"][0]["eyes"]["same"])

    def test_side_by_side_is_a_jpeg(self):
        out = refs.side_by_side(png(), png((0, 0, 255)))
        self.assertTrue(out.startswith(b"\xff\xd8"))

    def test_ui_wiring(self):
        for s in ("/api/refs/pin", "/api/refs/unpin", "📌 Use as reference", "🎭 Character sheet", "sheet: path"):
            self.assertIn(s, HTML)


class Strict(Refs):
    def test_card_down_never_falls_to_a_model_without_the_reference(self):
        """Live 2026-11-25: ComfyUI reset → venice/lustify-v8 without the reference → a stranger in the sheet."""
        self._local_up()
        picture_route.plan = lambda run, look, style, vm, forced: {"kind": "photo", "first": "local",
                                                                  "models": ["local/juggernaut-xl-v9", "venice/lustify-v8"]}

        class Down(RefMCP):
            def call(self, tool, args=None):
                if tool == "job_wait" and (args or {}).get("key") == "img:1":
                    self.calls.append(tool); self.args.append(args or {})
                    return {"state": "failed", "finished": True, "error": {"message": "Picture failed: [Errno 104] Connection reset by peer"}}
                return super().call(tool, args)
        mcp = Down()
        r = self._run(mcp)
        refs.pin(r.root, self._copy_pic(r.root))
        r.loop()
        makes = [a for t, a in zip(mcp.calls, mcp.args) if t == "image_make"]
        self.assertTrue(makes)
        self.assertTrue(all(m["model"] in refs.REF_MODELS and m.get("reference_images") for m in makes), makes)   # no juggernaut, no lustify
        self.assertEqual(r.state, "failed")
        self.assertIn("nothing was made without your reference", r.why)
        self.assertIn("Try again", r.why)
        self.assertLess(r.usd, 0.01)                                          # only the prompt writer, no picture paid for

    def test_no_reference_pinned_keeps_the_normal_fallback(self):
        self._local_up()
        picture_route.plan = lambda run, look, style, vm, forced: {"kind": "photo", "first": "local",
                                                                  "models": ["local/juggernaut-xl-v9", "venice/lustify-v8"]}
        mcp = RefMCP()
        r = self._run(mcp)
        r.loop()
        self.assertEqual(r.state, "done", r.why)
        # never Venice; a second juggernaut call is the 👁 $0 redo after a low score (follow-up 2026-11-25)
        self.assertEqual({a["model"] for t, a in zip(mcp.calls, mcp.args) if t == "image_make"}, {"local/juggernaut-xl-v9"})

    def test_same_face_line_is_written_even_when_the_check_breaks(self):
        r = self._run(RefMCP(), task="Character sheet of the person in this picture", batch_req={"n": 5, "sheet": "pictures/ref.png"})
        self._copy_pic(r.root)
        r.batch["items"] = [{"path": "pictures/ref.png", "k": i, "kind": "picture", "variation": f"view {i}"} for i in range(3)]
        calls = {"n": 0}
        orig = refs.same_face

        def flaky(run, src, raw, label):
            calls["n"] += 1
            if calls["n"] == 2:
                raise ConnectionResetError("hermes-mcp restarted")
            return {"score": 100, "same": True, "points": [{"ok": True}], "missing": []}
        refs.same_face = flaky
        self.addCleanup(lambda: setattr(refs, "same_face", orig))
        batch.same_faces(r)
        last = [s for s in r.steps if s["action"] == "eyes"][-1]
        self.assertIn("1 of 1 checked views match", last["why"])
        self.assertIn("2 not checked (ConnectionResetError: hermes-mcp restarted)", last["why"])

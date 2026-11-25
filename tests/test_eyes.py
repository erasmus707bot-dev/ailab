"""👁 Eyes M1 (Scott 2026-11-25): his words → yes/no points → match score + what is missing → 🔁 Fix and try again.
A check is $0, never fails a run, never spends; the improver sees the caption + score of kept / thrown results."""
import tempfile
from pathlib import Path
from types import SimpleNamespace

from ailab import agent, batch, config, eyes, shelf
from ailab.mcp_client import HermesRefused
from ailab.server import App
from tests.test_picture import Base, Brain, PicMCP

HTML = (Path(__file__).resolve().parent.parent / "ailab" / "web" / "index.html").read_text()


class FakeMCP:
    """Hermes with eyes: records every tool call; answers the points from `yes` (None = the model didn't say)."""
    def __init__(self, yes=None, caption="Two foxes in snow.", fail=None, refused=False):
        self.calls, self.yes, self.caption, self.fail, self.refused = [], yes, caption, fail, refused

    def call(self, tool, args=None):
        self.calls.append((tool, args or {}))
        if self.fail:
            raise self.fail
        if tool == "vision_check":
            self.points = args["points"]
            return {"ok": True, "key": "vis:1", "model": "qwen3.5:4b", "est_usd": 0.0}
        if tool == "job_wait":
            yes = self.yes if self.yes is not None else [True] * len(self.points)
            return {"state": "done", "finished": True, "result": {
                "model": "qwen3.5:4b", "caption": self.caption, "refused": self.refused, "usd": 0.0,
                "answers": [{"n": i + 1, "q": q, "yes": yes[i]} for i, q in enumerate(self.points)]}}
        raise AssertionError(f"eyes must not call {tool}")


def fake_run(mcp, cfg=None, root=None):
    r = SimpleNamespace(lab=SimpleNamespace(mcp=mcp), cfg=cfg or {}, connected=True, steps=[], usd=0.0, stage=None,
                        last_progress=0, root=root or Path(tempfile.mkdtemp()), pictures=[], batch=None, task="")
    r._check_stop = lambda: None
    r.save = lambda: None
    r._record = lambda st: r.steps.append(st)
    return r


def test_points_cover_subject_count_look_and_no_writing():
    pts = eyes.points("three red foxes in the snow, a wooden cabin behind them\nLook: Oil painting · Serene\nShape: Wide")
    kinds = [p["kind"] for p in pts]
    assert kinds == ["count", "show", "show", "look", "notext"], pts
    assert pts[0]["what"] == "exactly 3 red foxes" and "Count them" in pts[0]["q"]
    assert pts[1]["what"] == "in the snow" and pts[2]["what"] == "a wooden cabin behind them"
    assert pts[3]["what"] == "the Oil painting · Serene look"
    assert pts[-1]["want"] is False and "watermark" in pts[-1]["q"]                # yes here is the miss
    assert all("Shape" not in p["q"] and "Wide" not in p["q"] for p in pts)       # Lab lines are not his subject
    assert len(eyes.points(", ".join(f"thing number {i} here" for i in range(30)))) <= eyes.MAX_POINTS
    assert [p["kind"] for p in eyes.points("a girl with a red umbrella")] == ["show", "show", "notext"]
    assert eyes.points("2 cats")[0]["what"] == "exactly 2 cats"


def test_score_counts_only_what_the_model_answered():
    pts = eyes.points("three foxes, a cabin")                                      # count, show, notext
    s = eyes.score(pts, [False, True, False])
    assert s["score"] == 67 and s["missing"] == ["exactly 3 foxes"] and s["unsure"] == []
    s = eyes.score(pts, [True, None, True])                                        # text on the art = a miss; None left out
    assert s["score"] == 50 and s["missing"] == ["no writing on the art"] and s["unsure"] == ["a cabin"]
    assert eyes.score(pts, [None, None, None])["score"] is None
    assert eyes.score(pts, [])["score"] is None                                    # short answer list is not a crash


def test_fix_keeps_his_own_words_exactly_and_the_look():
    task = "Three  FOXES in *snow*, a cabin\nStyle: Painting\nShape: Wide\nLook: Oil painting · Serene"
    s = eyes.score(eyes.points(task), [False, True, True, True, True])            # count wrong + writing on it
    fixed = eyes.fix_task(task, s["points"])
    assert fixed.split("\n")[0] == "Three  FOXES in *snow*, a cabin"               # byte for byte
    assert "\nChange: there must be exactly 3 FOXES — count them; no written text, captions, logos or watermarks anywhere" in fixed
    assert fixed.endswith("\nStyle: Painting\nShape: Wide\nLook: Oil painting · Serene")
    again = eyes.fix_task("a fox\nChange: at dawn\nLook: Anime", [{"what": "a fox", "kind": "show", "ok": False}])
    assert again == "a fox\nChange: at dawn; clearly show a fox\nLook: Anime"     # an earlier change is kept
    assert eyes.fix_task(task, [{"what": "x", "kind": "show", "ok": True}]) == ""  # nothing missing → no fix offered


def test_check_flags_the_wrong_count_and_offers_the_fix_for_free():
    mcp = FakeMCP(yes=[False, True, False])                                        # asked for 3 foxes, got 2
    run = fake_run(mcp)
    e = eyes.check(run, b"picture-bytes", "three foxes, snow")
    assert e["score"] == 67 and e["missing"] == ["exactly 3 foxes"] and e["low"] is True
    assert e["fix_task"] == "three foxes, snow\nChange: there must be exactly 3 foxes — count them"
    assert e["caption"] == "Two foxes in snow." and e["model"] == "qwen3.5:4b"
    assert [c[0] for c in mcp.calls] == ["vision_check", "job_wait"]              # nothing that spends or makes
    assert run.usd == 0.0 and run.stage["icon"] == "👁"
    eyes.record(run, "picture", e)
    assert run.steps[-1]["usd"] == 0.0 and "67% match — missing: exactly 3 foxes" in run.steps[-1]["why"]
    assert eyes.check(fake_run(FakeMCP(yes=[True, False])), b"x", "a fox")["low"] is False         # 100% → no nagging


def test_a_broken_or_missing_vision_model_never_fails_the_run():
    off = HermesRefused("not_enabled", "The vision model qwen3.5:4b isn't on gandalf yet.", "On gandalf: ollama pull qwen3.5:4b")
    run = fake_run(FakeMCP(fail=off))
    e = eyes.check(run, b"x", "a fox")
    assert e == {"error": "The vision model qwen3.5:4b isn't on gandalf yet.", "fix": "On gandalf: ollama pull qwen3.5:4b"}
    eyes.record(run, "picture", e)
    assert "👉 On gandalf: ollama pull" in run.steps[-1]["why"]
    assert "error" in eyes.check(fake_run(FakeMCP(fail=ConnectionError("down"))), b"x", "a fox")
    assert "error" in eyes.check(fake_run(FakeMCP()), b"", "a fox")
    r = eyes.check(fake_run(FakeMCP(yes=[None, None], refused=True, caption="I can't describe this.")), b"x", "a fox")
    assert r["score"] is None and r["refused"] is True and r["fix_task"] == ""


def test_switch_and_standalone_turn_it_off():
    assert eyes.on(fake_run(FakeMCP())) is True
    assert eyes.on(fake_run(FakeMCP(), {"eyes": {"on": False}})) is False
    r = fake_run(FakeMCP())
    r.connected = False
    assert eyes.on(r) is False
    assert eyes.settings({"eyes": {"low": 50}})["low"] == 50 and eyes.settings(None) == {"on": True, "low": 70, "retry": None}


def test_batch_is_checked_after_it_is_made_and_the_best_is_starred():
    root = Path(tempfile.mkdtemp())
    (root / "pictures").mkdir()
    for n in ("a.png", "b.png", "c.png"):
        (root / "pictures" / n).write_bytes(b"png")
    answers = iter([[False, False], [True, False], [True, True]])                # a: 50, b: 100 (no text), c: 50

    class Seq(FakeMCP):
        def call(self, tool, args=None):
            if tool == "vision_check":
                self.yes = next(answers)
            return super().call(tool, args)
    run = fake_run(Seq(), root=root)
    run.task = "a fox"
    run.pictures = [{"path": f"pictures/{n}", "look": []} for n in ("a.png", "b.png", "c.png")]
    run.batch = {"dial": 0, "items": [{"path": p["path"], "k": i, "kind": "picture"} for i, p in enumerate(run.pictures)]}
    batch.look_at(run)
    scores = [it["eyes"]["score"] for it in run.batch["items"]]
    assert scores == [50, 100, 50] and [bool(it.get("best")) for it in run.batch["items"]] == [False, True, False]
    assert run.pictures[1]["eyes"]["score"] == 100 and "best match #2 at 100%" in run.steps[-1]["why"]
    off = fake_run(FakeMCP(fail=ConnectionError("down")), root=root)
    off.task, off.pictures = "a fox", run.pictures
    off.batch = {"dial": 0, "items": [{"path": "pictures/a.png", "k": 0, "kind": "picture"}, {"path": "pictures/b.png", "k": 1, "kind": "picture"}]}
    batch.look_at(off)
    assert len(off.lab.mcp.calls) == 1 and "eyes" not in off.batch["items"][1]     # one failed ask, then it stops asking


def test_improver_gets_caption_and_score_of_kept_and_thrown():
    d = Path(tempfile.mkdtemp())
    seen = eyes.seen([{"path": "p.png"}, {"path": "q.png", "eyes": {"score": 83, "caption": "A red fox by a lake at dawn.", "missing": []}}])
    assert seen == {"score": 83, "caption": "A red fox by a lake at dawn.", "missing": []}
    assert eyes.seen([{"eyes": {"error": "off"}}]) is None and eyes.seen([]) is None
    shelf.keep(d, "r1", "a red fox by a lake\nLook: Oil painting", [], seen)
    shelf.toss(d, "r2", "a grey city street", [], None, {"score": 40, "caption": "A street with a sign reading SALE.", "missing": ["no writing on the art"]})
    shelf.keep(d, "r3", "a wolf", [])                                              # not checked → the line stays as before
    taste = App._taste(d)
    assert taste["kept"] == ["a red fox by a lake [👁 83% match — it showed: A red fox by a lake at dawn.]", "a wolf"]
    assert taste["tossed"] == ["a grey city street [👁 40% match — it showed: A street with a sign reading SALE.]"]
    m = App._improve_msgs(App, {"ctypes": ["image"]}, "a bear", taste)[1]["content"]
    assert "83% match" in m and "A street with a sign reading SALE." in m
    assert shelf.view(d)["kept"][0]["seen"]["score"] == 83


def test_card_shows_score_missing_and_one_fix_button():
    assert "function eyesBox(e, fix)" in HTML and "🔁 Fix and try again" in HTML and "% match" in HTML
    assert HTML.count("eyesBox(") == 4                                             # the function + picture, video, batch tile
    assert "⭐ best match" in HTML and "eyeScore(y) - eyeScore(x)" in HTML          # batch: best first
    assert ".eyes .btn { min-height: 48px" in HTML and ".eyes summary { min-height: 48px" in HTML and "font-size: max(1rem, 23px)" in HTML
    box = HTML[HTML.index("function eyesBox"):HTML.index("function batchGrid")]
    assert "fix(e.fix_task)" in box and "api(" not in box and "fetch(" not in box  # the button only starts a normal run



class RealRun(Base):
    """End to end through agent.Run: picture made → 👁 looked at → score on the picture, in the why line, in view()."""
    def test_picture_run_is_checked_and_stays_done(self):
        class Hermes(PicMCP):
            def __init__(self):
                super().__init__(polls=1)
                self.eye = FakeMCP(yes=[False, True, False])                       # asked for 3 foxes, the model counts 2

            def call(self, tool, args=None):
                if tool == "vision_check" or (tool == "job_wait" and (args or {}).get("key") == "vis:1"):
                    self.calls.append(tool)
                    self.args.append(args or {})
                    return self.eye.call(tool, args)
                return super().call(tool, args)
        b = Brain(["Three foxes in the snow, soft light."])
        b.mcp = Hermes()
        r = agent.Run(b, config.load({"mode": "connected"}), self.project, "openrouter", "m", "three foxes, snow", ctypes=["image"], ask_first=False)
        r.loop()
        self.assertEqual(r.state, "done", r.why)
        pic = r.view()["pictures"][0]
        self.assertEqual((pic["eyes"]["score"], pic["eyes"]["missing"]), (67, ["exactly 3 foxes"]))
        self.assertIn("👁 67% match — missing: exactly 3 foxes", r.why)
        self.assertTrue(pic["eyes"]["fix_task"].startswith("three foxes, snow\nChange: there must be exactly 3 foxes"))
        self.assertEqual(b.mcp.calls.count("image_make"), 1)                       # the check made nothing new
        self.assertEqual(r.steps[-1]["action"], "eyes")
        self.assertEqual(r.steps[-1]["usd"], 0.0)

    def test_switched_off_means_no_look_at_all(self):
        b = Brain(["A fox."])
        b.mcp = PicMCP(polls=1)
        r = agent.Run(b, config.load({"mode": "connected", "eyes": {"on": False}}), self.project, "openrouter", "m", "a fox", ctypes=["image"], ask_first=False)
        r.loop()
        self.assertEqual(r.state, "done", r.why)
        self.assertNotIn("vision_check", b.mcp.calls)
        self.assertNotIn("eyes", r.view()["pictures"][0])


def test_a_fixed_task_is_checked_against_his_words_once():
    """Live 2026-11-25: the 🔁 fix's own Change line became extra points → "missing: exactly 7 foxes, exactly 7 foxes"."""
    task = "seven foxes sitting in a row in the snow"
    s = eyes.score(eyes.points(task), [False, True, True])
    fixed = eyes.fix_task(task, s["points"])
    assert [p["what"] for p in eyes.points(fixed)] == [p["what"] for p in eyes.points(task)]
    twice = eyes.fix_task(fixed, s["points"])                                     # fixing again stays one point each
    assert [p["kind"] for p in eyes.points(twice)] == ["count", "show", "notext"]
    own = eyes.points("a fox\nChange: at dawn; there must be exactly 2 foxes — count them; give it the Anime look")
    assert [p["what"] for p in own] == ["a fox", "at dawn", "no writing on the art"]   # his own change still counts
    assert [p["what"] for p in eyes.points("a fox, a fox")].count("a fox") == 1


def test_camera_moves_are_not_graded_but_framing_is():
    """Live 2026-11-25: a story still was marked "missing: slow push-in, tracking shot" — a still can't show a move."""
    whats = [p["what"] for p in eyes.points("Aria races down a wet street, close-up from the side, tracking shot, slow push-in")]
    assert whats == ["Aria races down a wet street", "close-up from the side", "no writing on the art"]
    assert [p["what"] for p in eyes.points("a fox, camera pans left")] == ["a fox", "no writing on the art"]
    assert "wide shot" in [p["what"] for p in eyes.points("a fox, wide shot")]
    assert "a panda eating bamboo" in [p["what"] for p in eyes.points("a panda eating bamboo")]   # "pan" inside a word stays

"""🏠 Drawn Looks → local SDXL on gandalf (2026-11-24): routed when up, Lustify otherwise, fallbacks, photo + switch-off."""
from __future__ import annotations

from ailab import agent, config, picture, picture_route
from ailab.mcp_client import HermesRefused
from tests.test_agent import Base, Brain
from tests.test_picture import PNG, PicMCP

LOCAL = {"id": "local/sdxl-base-1.0", "fits": True}


class LocalMCP(PicMCP):
    def __init__(self, models=(LOCAL,), refuse_local=False, fail_local=False):
        super().__init__()
        self.models, self.refuse_local, self.fail_local, self.last = list(models), refuse_local, fail_local, ""

    def call(self, tool, args=None):
        args = dict(args or {})                              # the picture run edits its args dict afterwards
        if tool == "image_models":
            self.calls.append(tool); self.args.append(args or {})
            return {"ok": True, "models": self.models}
        if tool == "image_make":
            m = (args or {}).get("model", "")
            if m.startswith("local/") and self.refuse_local:
                self.calls.append(tool); self.args.append(args or {})
                raise HermesRefused("not_enabled", "ComfyUI isn't running")
            self.last = m
        if tool == "job_wait" and self.last.startswith("local/") and self.fail_local:
            self.calls.append(tool); self.args.append(args or {})
            return {"ok": True, "state": "failed", "finished": True, "error": {"message": "out of memory"}}
        if tool == "job_wait":
            self.calls.append(tool); self.args.append(args or {})
            return {"ok": True, "state": "done", "finished": True,
                    "result": {"b64": PNG, "media_type": "image/png", "model": self.last, "usd": 0.0, "library": "", "prompt": "p"}}
        return super().call(tool, args)


class Route(Base):
    def setUp(self):
        super().setUp()
        picture_route.forget()

    def go(self, mcp, task, cfg=None):
        b = Brain(["soft light"]); b.mcp = mcp
        r = agent.Run(b, config.load({"mode": "connected", **(cfg or {})}), self.project, "openrouter", "coder/m", task, ctypes=["image"])
        r.loop()
        return r

    def models(self, mcp):
        return [a["model"] for t, a in zip(mcp.calls, mcp.args) if t == "image_make"]

    def test_drawn_look_goes_local(self):
        m = LocalMCP(); r = self.go(m, "a fox in snow\nLook: Watercolor · Serene")
        self.assertEqual(r.state, "done", r.why)
        self.assertEqual(self.models(m), ["local/sdxl-base-1.0"])
        self.assertIn("photograph", [a for t, a in zip(m.calls, m.args) if t == "image_make"][0]["negative_prompt"])

    def test_photo_look_stays_lustify(self):
        m = LocalMCP(); self.go(m, "a fox in snow\nLook: Photo · Golden hour")
        self.assertEqual(self.models(m), ["venice/lustify-v8"])

    def test_no_local_model_listed_stays_lustify(self):
        m = LocalMCP(models=[]); self.go(m, "a fox in snow\nLook: Watercolor")
        self.assertEqual(self.models(m), ["venice/lustify-v8"])

    def test_switch_off(self):
        m = LocalMCP(); self.go(m, "a fox in snow\nLook: Watercolor", cfg={"local_drawn": False})
        self.assertEqual(self.models(m), ["venice/lustify-v8"])

    def test_refused_falls_back_to_lustify(self):
        m = LocalMCP(refuse_local=True); r = self.go(m, "a fox in snow\nLook: Charcoal")
        self.assertEqual(r.state, "done", r.why)
        self.assertEqual(self.models(m), ["local/sdxl-base-1.0", "venice/lustify-v8"])   # refused, then Lustify

    def test_failed_card_job_retries_on_lustify(self):
        m = LocalMCP(fail_local=True); r = self.go(m, "a fox in snow\nLook: Watercolor")
        self.assertEqual(r.state, "done", r.why)
        self.assertEqual(self.models(m), ["local/sdxl-base-1.0", "venice/lustify-v8"])
        self.assertEqual(r.pictures[0]["model"], "venice/lustify-v8")

    def test_forced_model_wins(self):
        m = LocalMCP(); self.go(m, "a fox in snow\nLook: Watercolor", cfg={"picture_model": "venice/chroma"})
        self.assertEqual(self.models(m), ["venice/chroma"])


# ---- local pictures M3 (2026-11-24): route table, local-first / Venice-first, 🔑 keys line ----
ALL = [{"id": i, "fits": True} for i in ("local/flux2-klein-4b", "local/juggernaut-xl-v9", "local/pony-v6-xl",
                                         "local/illustrious-xl-v0.1", "local/sdxl-base-1.0")] + [{"id": "venice/lustify-v8"}]


class RouteM3(Route):
    def test_kinds(self):
        k = picture_route.kind
        self.assertEqual(k(["Photo"], ""), "photo")
        self.assertEqual(k(["Realism"], ""), "photo")
        self.assertEqual(k(["Anime", "Moody"], ""), "anime")
        self.assertEqual(k(["Manga"], ""), "anime")
        self.assertEqual(k(["Watercolor"], ""), "drawn")
        self.assertEqual(k([], ""), "plain")
        self.assertEqual(k([], "Photo-real"), "photo")
        self.assertEqual(k([], "anime"), "anime")
        self.assertEqual(k([], "Oil painting"), "drawn")

    def test_photo_goes_juggernaut(self):
        m = LocalMCP(models=ALL); r = self.go(m, "a fox in snow\nLook: Photo · Golden hour")
        self.assertEqual(self.models(m), ["local/juggernaut-xl-v9"])
        self.assertIn("none — $0", r.pictures[0]["keys"])
        self.assertIn("🔑 Keys this needs", r.why)

    def test_photo_falls_to_flux_when_juggernaut_missing(self):
        m = LocalMCP(models=[x for x in ALL if x["id"] != "local/juggernaut-xl-v9"])
        self.go(m, "a fox in snow\nLook: Photo")
        self.assertEqual(self.models(m), ["local/flux2-klein-4b"])

    def test_anime_goes_illustrious(self):
        m = LocalMCP(models=ALL); self.go(m, "a fox in snow\nLook: Anime")
        self.assertEqual(self.models(m), ["local/illustrious-xl-v0.1"])

    def test_plain_goes_flux(self):
        m = LocalMCP(models=ALL); self.go(m, "a fox in snow", cfg={"ask_first": False})
        self.assertEqual(self.models(m)[0], "local/flux2-klein-4b")

    def test_venice_first(self):
        m = LocalMCP(models=ALL); r = self.go(m, "a fox in snow\nLook: Anime", cfg={"picture_first": "venice"})
        self.assertEqual(self.models(m), ["venice/lustify-v8"])
        self.assertIn("Venice (in Hermes) — ✅ set", r.pictures[0]["keys"])

    def test_local_failure_skips_other_locals(self):
        m = LocalMCP(models=ALL, fail_local=True); r = self.go(m, "a fox in snow\nLook: Anime")
        self.assertEqual(r.state, "done", r.why)
        self.assertEqual(self.models(m), ["local/illustrious-xl-v0.1", "venice/lustify-v8"])   # not Pony too

    def test_first_setting_file(self):
        self.assertEqual(picture_route.set_first("venice")["first"], "venice")
        self.assertEqual(picture_route.first(), "venice")
        self.assertFalse(picture_route.set_first("cloud")["ok"])
        picture_route.set_first("local")
        self.assertEqual(picture_route.first(), "local")


from tests.test_server import Srv   # noqa: E402


class PictureFirstApi(Srv):
    def test_get_set(self):
        code, j, _ = self.req("/api/picture_first")
        self.assertEqual((code, j["first"], j["cfg"]), (200, "local", ""))
        code, j, _ = self.req("/api/picture_first", {"first": "venice"})
        self.assertEqual((code, j["first"]), (200, "venice"))
        self.assertEqual(self.req("/api/picture_first")[1]["first"], "venice")
        code, j, _ = self.req("/api/picture_first", {"first": "cloud"})
        self.assertEqual((code, j["ok"]), (400, False))

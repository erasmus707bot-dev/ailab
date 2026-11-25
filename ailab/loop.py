"""🔁 Loop — the Lab side of the Creative Loop (Phase 3, 2026-11-25). Design: ~/hermes/docs/CREATIVE_LOOP_DESIGN.md.

The spine lives in Hermes (forge/creative): this module only talks to it through MCP tools, and authors the
parameters for code-rendered pieces (ProReady motion primitives, code effects) with the model Scott picks.
Rating buttons on every output feed Hermes's ratings store. Standalone mode can't loop (no Hermes = no caps/log)."""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

from .mcp_client import HermesRefused

PRIMITIVES = ("tap-ripple", "current-flow", "packet-travel", "wave-propagate", "layer-peel", "bit-flip", "gauge-fill",
              "heat-airflow", "tree-expand", "scramble", "shield-block", "answer-pulse", "handshake", "spread",
              "seek-spin", "flow-steps")
AUTHOR_PROMPT = """You write ONE motion card as JSON for a study app. Nothing but the JSON.
Shape: {{"primitive": one of [{prims}], "v": 1, "params": {{...}}, "steps": [{{"on": "tap", "do": "advance"}}],
 "haptic": "tick"|"none", "sound": "blip"|"none", "alt": "one plain sentence saying what it shows", "fallback": "static"}}
Pick the primitive that teaches it best. params = the labels and numbers it needs (short words, true to the topic).
Topic: {goal}
This piece: {do}
Field: {field}"""
EFFECT_PROMPT = """Write ONE small interactive effect as JSON: {{"code": "<self-contained JS using only the DOM + Web
Animations API, under 3 KB, no network, respects prefers-reduced-motion>", "alt": "one plain sentence"}}. Nothing else.
Effect: {do} — for: {goal}"""
FIELDS = ("goal", "project", "field", "asset_type", "license_mode", "quality_bar", "budget_usd", "priority",
          "sensitive", "for_client", "tags", "image_model", "reference", "planner_model", "planner_provider")


class LoopError(Exception):
    def __init__(self, message: str, code: str = "bad_args", status: int = 400):
        super().__init__(message)
        self.code, self.status = code, status


def pictures_root() -> Path:
    base = Path(os.environ.get("HERMES_DATA", str(Path.home() / "hermes-data"))).expanduser()
    return Path(os.environ.get("HERMES_IMAGE_DIR", str(base / "images"))).expanduser()


def picture(rel: str) -> tuple[bytes, str]:
    """A loop output for the page: only a file under <hermes pictures>/ai-lab/, else (b'', '')."""
    try:
        root = pictures_root().resolve()
        rp = (root / str(rel)).resolve(strict=True)
    except (OSError, RuntimeError):
        return b"", ""
    ct = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}.get(rp.suffix.lower())
    if not ct or (root / "ai-lab") not in rp.parents or rp.stat().st_size > 15 * 1024 * 1024:
        return b"", ""
    return rp.read_bytes(), ct


def _json(text: str) -> dict:
    m = re.search(r"\{.*\}", text or "", re.S)
    if not m:
        raise LoopError("The model didn't give back JSON — try again or pick another model.", "bad_reply", 502)
    try:
        return json.loads(m.group(0))
    except ValueError:
        raise LoopError("The model's JSON was broken — try again.", "bad_reply", 502) from None


class Loop:
    def __init__(self, app):
        self.app = app

    @property
    def mcp(self):
        m = getattr(self.app.lab, "mcp", None)
        if m is None:
            raise LoopError("🔁 Loop needs Hermes (connected mode) — Hermes holds the caps, the recipe log and review.",
                            "standalone", 409)
        return m

    def _call(self, tool: str, args: dict) -> dict:
        try:
            return self.mcp.call(tool, args)
        except HermesRefused as e:
            raise LoopError(f"{e.message}" + (f" — {e.fix}" if e.fix else ""), e.code, 409) from None

    # ---- straight through to Hermes
    def plan(self, b: dict) -> dict:
        args = {k: b[k] for k in FIELDS if b.get(k) not in (None, "")}
        if not str(args.get("goal") or "").strip():
            raise LoopError("Say what you want made.")
        return self._call("creative_job_plan", args)

    def run(self, b: dict) -> dict:
        return self._call("creative_job_run", {"job_id": str(b.get("job_id") or ""), "payloads": b.get("payloads") or {}})

    def get(self, q: dict) -> dict:
        return self._call("creative_job_get", {"job_id": str((q.get("job_id") or [""])[0])})

    def jobs(self, q: dict) -> dict:
        return self._call("creative_jobs", {"limit": 30})

    def rate(self, b: dict) -> dict:
        return self._call("creative_rate", {"job_id": str(b.get("job_id") or ""), "piece": int(b.get("piece") or 0),
                                            "button": str(b.get("button") or ""), "reasons": list(b.get("reasons") or [])})

    def estimate(self, q: dict) -> dict:
        return self._call("creative_estimate", {"job_id": str((q.get("job_id") or [""])[0])})

    def spend_ok(self, b: dict) -> dict:
        return self._call("creative_spend_ok", {"job_id": str(b.get("job_id") or ""), "piece": int(b.get("piece") or 0),
                                                "pin": str(b.get("pin") or "")})

    def trust(self, q: dict) -> dict:
        return self._call("trust_list", {})

    # ---- the Lab's own creative work: author code-rendered pieces
    def author(self, b: dict) -> dict:
        job = self._call("creative_job_get", {"job_id": str(b.get("job_id") or "")})["job"]
        n = int(b.get("piece") or 0)
        piece = next((p for p in job["pieces"] if p["n"] == n), None)
        if not piece or piece.get("method") not in ("proready.primitive", "lab.code_effect"):
            raise LoopError("Only motion primitives and code effects are written here.")
        prov, model = str(b.get("provider") or ""), str(b.get("model") or "")
        if not prov or not model:
            raise LoopError("Pick a model to write it with.")
        effect = piece["method"] == "lab.code_effect"
        prompt = (EFFECT_PROMPT if effect else AUTHOR_PROMPT).format(
            prims=", ".join(PRIMITIVES), goal=job["goal"], do=piece["do"], field=job.get("field") or "-")
        project = {"name": f"loop-{job['id']}", "sensitive": bool(job.get("sensitive"))}
        r = self.app.lab.chat(project, prov, model, [{"role": "user", "content": prompt}], 900, task="creative_author")
        payload = _json(r.text)
        if not effect and payload.get("primitive") not in PRIMITIVES:
            raise LoopError(f"The model picked {payload.get('primitive')!r}, which isn't one of the 16 — try again.",
                            "bad_reply", 502)
        return {"ok": True, "piece": n, "payload": payload, "usd": r.usd}

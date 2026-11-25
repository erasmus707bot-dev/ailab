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


class _Shim:
    """Just enough of a run for craft.for_run: an id, the config, a step list."""
    def __init__(self, rid: str, cfg: dict):
        self.id, self.cfg, self.steps, self.craft_used = rid, cfg, [], []

    def _record(self, row: dict) -> None:
        self.steps.append(row)


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
        jid, pls = str(b.get("job_id") or ""), dict(b.get("payloads") or {})
        if (getattr(self.app, "cfg", None) or {}).get("loop_writer", True) is not False:
            try:
                pls = self.write_prompts(self._call("creative_job_get", {"job_id": jid})["job"], pls)
            except Exception:                                   # noqa: BLE001 — a missing prompt falls back to Hermes's own
                pass
        return self._call("creative_job_run", {"job_id": jid, "payloads": pls})

    # ---- 📓 Loop pictures get the Lab's writer (Craft Book notes + 🔢 count layout), 2026-11-25
    def write_prompts(self, job: dict, pls: dict) -> dict:
        """Every 🖼 lab.image piece not yet made gets a written prompt in its payload; Hermes uses it instead of
        "do — goal". Notes used are remembered as run "loop:<job>:<n>" so ✅/🔁/❌ ratings count on them."""
        for piece in job.get("pieces") or []:
            n = piece.get("n")
            if piece.get("method") != "lab.image" or piece.get("state") in ("done", "running") \
                    or pls.get(str(n)) is not None or pls.get(n) is not None:
                continue
            text = self.write_one(job, piece)
            if text:
                pls[str(n)] = {"prompt": text[:1500]}
        return pls

    def write_one(self, job: dict, piece: dict) -> str:
        from . import craft, picture                            # noqa: PLC0415
        words = f"{piece.get('do') or ''} — {job.get('goal') or ''}".strip(" —")
        shim = _Shim(f"loop:{job.get('id')}:{piece.get('n')}", self.app.cfg)
        sys = picture.PROMPT_SYS + craft.for_run(shim, "picture", words)
        project = {"id": f"loop-{job.get('id')}", "name": f"loop-{job.get('id')}", "sensitive": bool(job.get("sensitive"))}
        lay = picture.count_layout(words)
        head = f"{words.rstrip('.')}." + (f" {lay}" if lay else "")
        cfg_w = [tuple(w) for w in (self.app.cfg.get("picture_writers") or []) if isinstance(w, (list, tuple)) and len(w) == 2]
        provs = getattr(self.app.lab, "providers", {}) or {}
        for prov, model in [w for w in (cfg_w or list(picture.WRITERS)) if w[0] in provs]:
            try:
                r = self.app.lab.chat(project, prov, model, [{"role": "system", "content": sys},
                                                             {"role": "user", "content": words}], 300, cap_usd=0.05,
                                      task="creative_prompt")
            except Exception:                                   # noqa: BLE001 — privacy / cap / provider: try the next
                continue
            add = re.sub(r"^\s*(prompt|details?)\s*:\s*", "", (r.text or "").strip(), flags=re.I).strip().strip('"').strip()
            if add.lower().startswith(words.lower()):
                add = add[len(words):].lstrip(" ,.;:-").strip()
            if 5 <= len(add) <= 1200 and not picture.REFUSAL_RX.search(add[:80]):
                return f"{head} {add}"
        return head if lay else ""                              # no writer: only worth sending when it adds the layout

    def get(self, q: dict) -> dict:
        return self._call("creative_job_get", {"job_id": str((q.get("job_id") or [""])[0])})

    def jobs(self, q: dict) -> dict:
        return self._call("creative_jobs", {"limit": 30})

    def rate(self, b: dict) -> dict:
        jid, n, button = str(b.get("job_id") or ""), int(b.get("piece") or 0), str(b.get("button") or "")
        out = self._call("creative_rate", {"job_id": jid, "piece": n, "button": button, "reasons": list(b.get("reasons") or [])})
        if button in ("keep", "redo", "wrong"):                 # 📓 ✅ = kept, 🔁/❌ = thrown away, on the notes it used
            from . import craft                                 # noqa: PLC0415
            craft.verdict(f"loop:{jid}:{n}", button == "keep")
        return out

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

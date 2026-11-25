"""One-shot patch for M4/M5 (2026-11-24). Run from ~/ailab: python3 /path/patch_m4.py"""
from pathlib import Path

R = Path(".")


def sub(path, old, new, count=1):
    p = R / path
    t = p.read_text()
    if new in t:
        print(f"skip (already) {path}")
        return
    assert t.count(old) == count, f"{path}: expected {count} of {old[:60]!r}, found {t.count(old)}"
    p.write_text(t.replace(old, new))
    print(f"ok {path}")


# ---- config: free ports, guard settings, self link
sub("ailab/config.py",
    '    "live_ports": [8860, 8861],          # Now, New — unused in ~/hermes (grep 2026-11-23); UNVERIFIED on the live box\n',
    '    "live_ports": [8862, 8863],          # Now, New — moved off 8860/8861 2026-11-24 (🛡 Guard owns 8860)\n'
    '    # 🛡 Guard (2026-11-24): the Lab may change these programs only through the walled-off Guard (root, 8860).\n'
    '    "guard_url": "http://127.0.0.1:8860",\n'
    '    "guard_public_url": "https://gandalf-nuc11phi7.tail5f20a0.ts.net:8860/",\n'
    '    "guard_watch_minutes": 5,\n'
    '    "guarded": {"ailab": str(REPO), "hermes": str(Path.home() / "hermes")},\n')
sub("ailab/config.py",
    '    if cfg["mode"] not in ("standalone", "connected"):\n',
    '    repos = dict(cfg.get("repos") or {})                   # 2026-11-24: the Lab can read + propose to itself\n'
    '    repos.setdefault("ailab", str(REPO))\n'
    '    cfg["repos"] = repos\n'
    '    if cfg["mode"] not in ("standalone", "connected"):\n')

# ---- review: guarded apply
sub("ailab/review.py", "from . import agent, config, preview, store\n",
    "from . import agent, config, guardlink, preview, store\n")
sub("ailab/review.py",
    '        rows.append({**r, "sha": hashlib.sha256(text.encode()).hexdigest(), "preview": text[:4000],\n'
    '                     "target": str(t), "new": cur is None, "diff": agent.make_diff(t.name, cur, text)})\n',
    '        g = guardlink.program_of(config.load(), t)\n'
    '        rows.append({**r, "sha": hashlib.sha256(text.encode()).hexdigest(), "preview": text[:4000],\n'
    '                     "target": str(t), "new": cur is None, "diff": agent.make_diff(t.name, cur, text),\n'
    '                     "guarded": g[0] if g else ""})\n')
sub("ailab/review.py",
    '    if not parts or any(p.startswith(".") for p in parts):\n',
    '    if guardlink.is_guard_path(t):\n'
    '        raise ReviewError("The 🛡 Guard\'s own files are never written from the Lab.", "guard", "🛡")\n'
    '    if not parts or any(p.startswith(".") for p in parts):\n')
sub("ailab/review.py",
    '    text = _content(aid).read_text()\n'
    '    if hashlib.sha256(text.encode()).hexdigest() != sha:\n'
    '        raise ReviewError("It changed since you looked — reload and check it again.", "stale", "🔁")\n'
    '    t = _safe_target(target(item))\n',
    '    text = _content(aid).read_text()\n'
    '    if hashlib.sha256(text.encode()).hexdigest() != sha:\n'
    '        raise ReviewError("It changed since you looked — reload and check it again.", "stale", "🔁")\n'
    '    t = _safe_target(target(item))\n'
    '    if guardlink.program_of(config.load(), t):                     # 🛡 the Lab or Hermes → only through the Guard\n'
    '        return apply_group([{"id": aid, "sha": sha}], confirm)\n')
sub("ailab/review.py",
    'def reject(aid: str) -> dict:\n',
    '''def apply_group(picks: list[dict], confirm: str, runner=None) -> dict:
    """🛡 Apply changes to the Lab or Hermes together: prove → Guard copy → watch → write → restart (guardlink)."""
    if str(confirm or "").strip().lower() != APPLY_WORD:
        raise ReviewError(f'Type "{APPLY_WORD}" to write the files.', "confirm", "✋")
    cfg = config.load()
    waiting = {r["id"]: r for r in agent.approvals("waiting")}
    groups: dict[str, dict] = {}
    plain: list[dict] = []
    for pk in picks[:40]:
        aid, sha = str(pk.get("id") or ""), str(pk.get("sha") or "")
        item = waiting.get(aid)
        if not item:
            raise ReviewError("One of those isn't waiting any more — reload.", "state", "📋")
        text = _content(aid).read_text()
        if hashlib.sha256(text.encode()).hexdigest() != sha:
            raise ReviewError("One changed since you looked — reload and check it again.", "stale", "🔁")
        t = _safe_target(target(item))
        g = guardlink.program_of(cfg, t)
        if not g:
            plain.append(pk)
            continue
        name, root = g
        grp = groups.setdefault(name, {"root": root, "items": []})
        grp["items"].append({"id": aid, "target": t, "rel": str(t.relative_to(root)), "text": text})
    done = []
    for name, grp in groups.items():
        changes = {x["rel"]: x["text"] for x in grp["items"]}
        try:
            checks = guardlink.prove(cfg, name, grp["root"], changes, runner=runner)
        except guardlink.ProofFailed as e:
            raise ReviewError(f"🧪 Not written — {e}", "proof", "🧪") from e
        except Exception as e:  # noqa: BLE001 — e.g. no sandbox: new code never runs unsandboxed
            raise ReviewError(f"🧪 The tests couldn't run ({e}) — not written.", "proof", "🧪") from e
        why = f"before a Lab change: {', '.join(sorted(changes))[:200]}"
        try:
            sid = guardlink.snap(cfg, name, why)
            guardlink.watch(cfg, name, sid, why)
        except guardlink.GuardDown as e:
            raise ReviewError(str(e), "guard_down", "🛡") from e
        written = []
        try:
            for x in grp["items"]:
                t = x["target"]
                t.parent.mkdir(parents=True, exist_ok=True)
                tmp = t.with_name(f".{t.name}.ailab-{x['id']}")
                tmp.write_text(x["text"])
                os.replace(tmp, t)
                if t.read_text() != x["text"]:
                    raise OSError(f"{t.name} doesn't read back the same")
                written.append(x)
        except OSError as e:
            try:
                guardlink.restore(cfg, name, sid)
                why2 = "the Guard put everything back"
            except guardlink.GuardDown:
                why2 = "and the Guard couldn't put it back — open 🛟"
            raise ReviewError(f"Writing stopped half-way ({e}); {why2}.", "write", "⚠️") from e
        for x in written:
            agent.set_approval_state(x["id"], "applied", target=str(x["target"]), backup=f"guard:{name}:{sid}")
        guardlink.restart_later(cfg, name)
        done.append({"program": name, "files": [x["rel"] for x in written], "guard_copy": sid, "checks": checks,
                     "watching_minutes": cfg.get("guard_watch_minutes") or 5})
    for pk in plain:
        done.append({"program": "", **apply(str(pk["id"]), str(pk["sha"]), confirm)})
    return {"ok": True, "state": "applied", "done": done,
            "guarded": [d["program"] for d in done if d.get("program")]}


def reject(aid: str) -> dict:
''')

# ---- server: health, guard state, group apply
sub("ailab/server.py",
    '    def review_reject(self, b: dict) -> tuple[int, dict]:\n',
    '    def review_apply_group(self, b: dict) -> tuple[int, dict]:\n'
    '        return 200, review.apply_group(list(b.get("items") or []), str(b.get("confirm") or ""))\n\n'
    '    def guard_state(self, q: dict) -> tuple[int, dict]:\n'
    '        s = guardlink.state(self.cfg)\n'
    '        return 200, {**s, "public_url": self.cfg.get("guard_public_url") or ""}\n\n'
    '    def review_reject(self, b: dict) -> tuple[int, dict]:\n')
sub("ailab/server.py",
    '            if p == "/api/review/reject":\n',
    '            if p == "/api/review/apply_group":\n'
    '                return self._run(app.review_apply_group, b)\n'
    '            if p == "/api/review/reject":\n')
sub("ailab/server.py",
    '            if u.path == "/api/agent/approvals":\n',
    '            if u.path == "/api/health":                          # 🛡 the Guard watches this\n'
    '                return self._run(lambda: (200, {"ok": True, "app": "ailab"}))\n'
    '            if u.path == "/api/guard":\n'
    '                return self._run(app.guard_state, q)\n'
    '            if u.path == "/api/agent/approvals":\n')

sub("ailab/server.py", "               robotcheck, roster, store)\n", "               robotcheck, roster, store, guardlink)\n")

"""🤖 Robot check for 🪞 Show & change (2026-11-23, AI Lab fix 4) — makes the 🚦 light honest.

A real headless browser opens the Now and New pages, finds the spot Scott pointed at, checks it really changed,
clicks it on the New (test copy) side only when it is clickable, and compares page errors. The light may only go green when this passes.
If the robot can't run (Playwright or a browser missing, app asks for a sign-in), it says so and the light stays
yellow — never green on a guess.

Safety: the robot NEVER clicks the Now (real) page — a click there runs real actions (2026-11-24: it started a
real Hermes scan). New is look-only (non-GET → 403 at the proxy) unless Scott ticked 🔓, so a click cannot save
anything; that expected 403 is not counted as a new error.
The browser is headless, has no cookies of Scott's and only visits the two loopback preview ports.
Needs on gandalf: `pip install --user playwright` — it drives the Chrome already installed (no browser download).
"""
from __future__ import annotations

import shutil
import time
from pathlib import Path

LOOKONLY_403 = "status of 403"   # console text when New's look-only proxy refuses a save — expected, not a bug
LOAD_FAIL = "Failed to load resource"  # after New's click: fallout of the blocked save (403, then 404 polls) — a note
CLICKABLE = ("button", "a", "summary", "label", "select", "input")
TIMEOUT_MS = 15_000


def browser_path(cfg: dict | None = None) -> str | None:
    """Chrome / Chromium on this machine (config "robot_browser" wins)."""
    want = (cfg or {}).get("robot_browser") or ""
    if want and Path(want).is_file():
        return want
    for n in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome"):
        p = shutil.which(n)
        if p:
            return p
    return None


def available(cfg: dict | None = None) -> tuple[bool, str]:
    try:
        import playwright.sync_api  # noqa: F401, PLC0415
    except ImportError:
        return False, "The robot test needs Playwright. On gandalf: pip install --user playwright"
    if not browser_path(cfg):
        return True, "no system Chrome — using Playwright's own browser if it was installed"
    return True, ""


# ---------- what the robot does on one page (JS run inside the page) ----------
_PROBE = """sel => { const el = sel ? document.querySelector(sel) : null;
  if (!el) return {found: false, text: (document.body ? document.body.innerText : '').slice(0, 20000)};
  const r = el.getBoundingClientRect(), s = getComputedStyle(el);
  return {found: true, tag: el.tagName.toLowerCase(), visible: !!(r.width && r.height) && s.visibility !== 'hidden' && s.display !== 'none',
          html: el.outerHTML.slice(0, 4000), text: (el.innerText || el.value || '').slice(0, 500),
          box: [Math.round(r.width), Math.round(r.height)],
          style: [s.color, s.backgroundColor, s.fontSize, s.fontWeight, s.borderColor, s.padding, s.display].join('|'),
          disabled: !!el.disabled}; }"""
_SIGNIN = """() => !!document.querySelector('input[type=password]') || /sign in|log in|owner key|unauthori[sz]ed/i.test((document.title || '') + ' ' + (document.body ? document.body.innerText.slice(0, 400) : ''))"""


def _visit(ctx, url: str, sel: str, click: bool, shot: Path | None) -> dict:
    page = ctx.new_page()
    errs: list[str] = []
    page.on("pageerror", lambda e: errs.append(str(e)[:200]))
    page.on("console", lambda m: errs.append(m.text[:200]) if m.type == "error" else None)
    out: dict = {"url": url}
    try:
        resp = page.goto(url, wait_until="load", timeout=TIMEOUT_MS)
        out["status"] = resp.status if resp else None
        page.wait_for_timeout(800)                                   # let page scripts settle
        out["signin"] = bool(page.evaluate(_SIGNIN))
        out["probe"] = page.evaluate(_PROBE, sel or None)
        out["errors_before"] = list(errs)
        if click and out["probe"].get("found") and out["probe"].get("visible") and not out["probe"].get("disabled") \
                and out["probe"].get("tag") in CLICKABLE:
            try:
                page.locator(sel).first.click(timeout=5000)
                page.wait_for_timeout(800)
                out["clicked"] = True
            except Exception as e:                                   # noqa: BLE001 — a failed click is a finding
                out["clicked"], out["click_error"] = False, str(e).splitlines()[0][:200]
        if shot:
            page.screenshot(path=str(shot), full_page=False)
            out["shot"] = shot.name
    except Exception as e:                                           # noqa: BLE001
        out["load_error"] = str(e).splitlines()[0][:200]
    out["errors"] = list(errs)
    page.close()
    return out


def run(now_url: str, new_url: str, selector: str = "", shots: Path | None = None, cfg: dict | None = None,
        driver=None) -> dict:
    """→ {"ran", "ok", "level": green|yellow|red, "why": [...], "now", "new"}. `driver(now_url, new_url, sel, shots)`
    can replace the real browser in tests."""
    sel = (selector or "").strip()[:300]
    if driver is None:
        ok, msg = available(cfg)
        if not ok:
            return {"ran": False, "ok": False, "level": "yellow", "why": [f"🤖 Robot test did not run: {msg}"]}
        driver = _real
    try:
        now, new = driver(now_url, new_url, sel, shots, cfg)
    except Exception as e:                                           # noqa: BLE001
        return {"ran": False, "ok": False, "level": "yellow",
                "why": [f"🤖 Robot test could not start the browser: {str(e).splitlines()[0][:200]}"]}
    return judge(now, new, sel)


def _real(now_url, new_url, sel, shots, cfg):
    from playwright.sync_api import sync_playwright  # noqa: PLC0415
    exe = browser_path(cfg)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    if shots:
        shots.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        b = pw.chromium.launch(headless=True, **({"executable_path": exe} if exe else {}))
        try:
            ctx = b.new_context(viewport={"width": 1280, "height": 900})
            now = _visit(ctx, now_url, sel, False, shots / f"{stamp}-now.png" if shots else None)
            new = _visit(ctx, new_url, sel, True, shots / f"{stamp}-new.png" if shots else None)
        finally:
            b.close()
    return now, new


def judge(now: dict, new: dict, sel: str) -> dict:
    red, yellow, good = [], [], []
    if new.get("load_error"):
        red.append(f"The robot could not open the New page: {new['load_error']}")
    elif (new.get("status") or 0) >= 400 and not (now.get("status") or 0) >= 400:
        red.append(f"The New page did not open (the app answered {new['status']}).")
    if now.get("signin") or new.get("signin"):
        yellow.append("The app asked the robot to sign in, so it could not see the real page. Check it yourself.")
    # Now is never clicked, so: load errors compare New vs Now; errors after New's click must be none
    # (except the look-only 403, which is the safety block working).
    now_errs = now.get("errors_before", now.get("errors")) or []
    new_load = new.get("errors_before", new.get("errors")) or []
    new_click = (new.get("errors") or [])[len(new_load):] if "errors_before" in new else []
    blocked = [e for e in new_click if LOOKONLY_403 in e or LOAD_FAIL in e]
    fresh = [e for e in new_load if e not in now_errs] + [e for e in new_click if e not in blocked]
    if blocked:
        good.append("The click tried to save something; the test copy blocked it, as it should.")
    if fresh:
        red.append(f"New error on the page: {fresh[0]}" + (f" (+{len(fresh) - 1} more)" if len(fresh) > 1 else ""))
    pn, pw = now.get("probe") or {}, new.get("probe") or {}
    if sel:
        if not pw.get("found"):
            yellow.append("The spot you pointed at is not on the New page any more (it may have moved or been renamed).")
        elif not pw.get("visible"):
            red.append("The spot you pointed at is hidden on the New page.")
        else:
            same = pn.get("found") and all(pn.get(k) == pw.get(k) for k in ("html", "style", "box"))
            if same:
                red.append("The spot you pointed at looks exactly the same on the New page — the change didn't land there.")
            else:
                good.append("The spot you pointed at changed.")
            if new.get("clicked") is False:
                red.append(f"The robot could not click it on the New page: {new.get('click_error', '')}")
            elif new.get("clicked"):
                good.append("The robot clicked it and the page kept working.")
    else:
        if pn.get("text") == pw.get("text"):
            yellow.append("The robot saw no visible difference between Now and New.")
        else:
            good.append("The page text changed.")
        yellow.append("Point 👆 at the spot next time so the robot can test that exact part.")
    level = "red" if red else "yellow" if yellow else "green"
    return {"ran": True, "ok": level == "green", "level": level, "why": red + yellow, "good": good,
            "shots": [x for x in (now.get("shot"), new.get("shot")) if x]}

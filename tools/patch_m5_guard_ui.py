"""M5 screen part (2026-11-24): 🛡 badge, Apply-all-together, 👀 watching line, 🛟 link. Run from ~/ailab."""
from pathlib import Path

p = Path("ailab/web/index.html")
t = p.read_text()


def sub(old, new):
    global t
    if new in t:
        print("skip (already)")
        return
    assert t.count(old) == 1, f"expected 1 of {old[:70]!r}, found {t.count(old)}"
    t = t.replace(old, new)
    print("ok")


GUARD_MSG = ('function guardMsg(a) { return a.ok && (a.guarded || []).length ? `✅ written · 🛡 copy saved · 👀 watching '
             '${(a.done || [])[0]?.watching_minutes || 5} min · 🔄 restarting — it goes back by itself if it breaks` : null; }\n')

# workbench rows: badge + guarded apply message
sub('''      rows.push(chgCard("✋", x.target, `${x.new ? "new file" : "change"} to real code · from ${x.project}${x.note ? " · " + x.note : ""} · not written yet`, x.diff || x.preview, true, cf,
        h("button", { class: "btn pri", onclick: async () => {
          const a = await api("/api/review/apply", { id: x.id, sha: x.sha, confirm: cf.value });
          note.textContent = a.ok ? `✅ written${a.backup ? " (old copy kept)" : ""}` : `${a.icon || "⚠️"} ${a.message}`; if (a.ok) setTimeout(loadHeld, 700);''',
    '''      const gd = x.guarded ? ` · 🛡 ${x.guarded === "ailab" ? "the Lab itself" : "Hermes"} — tested first, a copy is saved, it undoes itself if it breaks` : "";
      rows.push(chgCard(x.guarded ? "🛡" : "✋", x.target, `${x.new ? "new file" : "change"} to real code · from ${x.project}${x.note ? " · " + x.note : ""} · not written yet${gd}`, x.diff || x.preview, true, cf,
        h("button", { class: "btn pri", onclick: async () => {
          if (x.guarded) note.textContent = "🧪 testing it in a safe copy first — can take a few minutes…";
          const a = await api("/api/review/apply", { id: x.id, sha: x.sha, confirm: cf.value });
          note.textContent = guardMsg(a) || (a.ok ? `✅ written${a.backup ? " (old copy kept)" : ""}` : `${a.icon || "⚠️"} ${a.message}`); if (a.ok) setTimeout(loadHeld, 700);''')

# workbench header: apply-all + guard line
sub('''    changes.innerHTML = "";
    if (rows.length) changes.append(h("h2", {}, `✋ ${rows.length} waiting for your OK`),
      h("p", { class: "panesub" }, "Read what changed, then Apply (type apply) or Reject. Nothing touches your real code until you do."), ...rows);''',
    '''    changes.innerHTML = "";
    const gHeld = held.filter(x => x.guarded);
    let allRow = null;
    if (gHeld.length > 1) {
      const cfa = h("input", { type: "text", "aria-label": "Type apply", placeholder: "type apply" }), na = h("span", { class: "note" });
      allRow = h("div", { class: "runbar" }, cfa, h("button", { class: "btn pri", onclick: async () => {
        na.textContent = "🧪 testing all of them together in a safe copy — can take a few minutes…";
        const a = await api("/api/review/apply_group", { items: gHeld.map(x => ({ id: x.id, sha: x.sha })), confirm: cfa.value });
        na.textContent = guardMsg(a) || `${a.icon || "⚠️"} ${a.message}`; if (a.ok) setTimeout(loadHeld, 700);
      } }, `🛡 Apply all ${gHeld.length} together`), na);
    }
    if (rows.length) changes.append(h("h2", {}, `✋ ${rows.length} waiting for your OK`),
      h("p", { class: "panesub" }, "Read what changed, then Apply (type apply) or Reject. Nothing touches your real code until you do."), ...[guardLine, allRow].filter(Boolean), ...rows);
    else if (guardLine) changes.append(guardLine);''')

# workbench: guard line state + loader
sub('''  async function loadHeld() {
    const r = await api(`/api/review?project=${encodeURIComponent(p.id)}`);
    held = r.ok ? (r.held || []) : []; paintChanges();
  }''',
    '''  ''' + GUARD_MSG + '''  var guardLine = h("p", { class: "panesub", id: "guardline" });
  async function loadGuard() {
    const g = await api("/api/guard");
    const link = g.public_url ? h("a", { href: g.public_url, target: "_blank", rel: "noopener", class: "chip" }, "🛟 Rollback page") : null;
    if (!g.ok || !g.up) { guardLine.replaceChildren("🛡 The Guard isn't answering — changes to the Lab and Hermes are blocked until it is. ", link || ""); return; }
    const w = (g.targets || []).filter(t => t.watch).map(t => `👀 watching ${t.label} — ${Math.max(0, Math.round((t.watch.until * 1000 - Date.now()) / 60000))} min left`);
    guardLine.replaceChildren(w.length ? w.join(" · ") + " · " : "🛡 Guard on · ", link || "");
  }
  async function loadHeld() {
    const r = await api(`/api/review?project=${encodeURIComponent(p.id)}`);
    held = r.ok ? (r.held || []) : []; paintChanges(); loadGuard();
  }''')

# Review page rows: guarded message too
sub('''        const a = await api("/api/review/apply", { id: x.id, sha: x.sha, confirm: cf.value });
        note.textContent = a.ok ? `✅ written${a.backup ? " (old copy kept)" : ""}` : `${a.icon || "⚠️"} ${a.message}`;
        if (a.ok) setTimeout(load, 900);''',
    '''        if (x.guarded) note.textContent = "🧪 testing it in a safe copy first — can take a few minutes…";
        const a = await api("/api/review/apply", { id: x.id, sha: x.sha, confirm: cf.value });
        note.textContent = (a.ok && (a.guarded || []).length) ? "✅ written · 🛡 copy saved · 👀 watching · 🔄 restarting" : a.ok ? `✅ written${a.backup ? " (old copy kept)" : ""}` : `${a.icon || "⚠️"} ${a.message}`;
        if (a.ok) setTimeout(load, 900);''')
sub('''        h("div", { class: "why" }, `From the agent in ${x.project} · ${x.bytes} bytes · outside the project folder`),''',
    '''        h("div", { class: "why" }, `From the agent in ${x.project} · ${x.bytes} bytes · outside the project folder${x.guarded ? " · 🛡 guarded (tested, copied, undoes itself if it breaks)" : ""}`),''')

p.write_text(t)

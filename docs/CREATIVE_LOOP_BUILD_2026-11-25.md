# Creative Loop Build — Hermes × AI Lab × ProReady

**Written:** 2026-11-25 · **v1.1** (same day: Phase 0 findings + the hands-off rule)
**Venue:** Claude Cowork, device shell into gandalf-NUC (user `gandalf`)
**Repos (confirmed in Phase 0):** Hermes `~/hermes` (data in `~/hermes-forge`) · AI Lab `~/ailab` (its own repo, connected to Hermes over the MCP server `~/hermes/forge/projects/mcp_server.py`) · ProReady `~/SonoVault` (live; `~/SonoVault-prisma7` is an older side copy, don't build there)
**First job:** upgrade ProReady's IT study material (A+, Linux+, Security+) with tactile, physical-feeling visuals and motion.
**Continue phrase:** `continue Creative Loop from the 2026-11-25 build prompt`

---

## 0. Standing rules (read first, apply throughout)

### 0.1 Token-saving standard (permanent)
- Do the work, then return a **short report**: what changed, files touched, test results, blockers, and the next phase's model.
- If a step is already done and verified, **skip it**: "already present — skipped", in one line.
- No narration, no file dumps, and no recap of this prompt. Long logs go inside `<details>`.

### 0.2 Project standard wins
- If a repo's `CLAUDE.md` names a ledger, inbox or standard, follow it first. For Hermes these are `SESSION-LEDGER.md` and `docs/TOKEN_EFFICIENCY_STANDARD.md`.
- In ProReady, the **Master Build Prompt plus `DECISIONS.md`** is the spec, and a dated decision overrides the spec.
- Where any of these conflicts with this prompt, **flag the conflict**. Never pick silently.

### 0.3 Permission gates
- Stop at the end of every phase. Post the report, then ask:
  - After Phase 1: **"Would you like me to proceed with the final build based on this outline?"**
  - After later phases: **"Proceed to Phase N? (model: X)"**
- Stop immediately, even after "go", for anything irreversible: destructive migrations, deletes, new remotes, live-service restarts, or any write into ERASMUS before 2027-01-01. List the planned change, then wait.

### 0.4 Handoffs as you go
- After each finished phase, write `HANDOFF_<YYYY-MM-DD>_creative-loop.md`. It holds the commit hashes, what's done, the next phase, the next model and the exact continue phrase.
- If a session stops with phases left, end the handoff with the **night tail** JSON block. It follows the format in Hermes `prompts/HERMES_SESSION_INIT.md` § Night tail: ONE next phase, `prompt_file`, `prompt_anchor` and `acceptance[]`. Validate it with `python3 -m forge.night.tail --root . --all-dates`.

### 0.5 Device-shell quirks (`mcp__remote-devices__*`)
- Run read-only git as `GIT_OPTIONAL_LOCKS=0 git ...`.
- Before the first `add` or `commit` in each repo, request delete permission on the repo root once. Run `rm -f .git/index.lock` after every git sequence.
- Copy files **sequentially**. `md5sum` each one against its source before `git add`. On a mismatch, retry the copy. Never commit an unverified file.
- The shell has **no network**, no process view, and can't reach `~/.claude`, crontab, services or `~/Dropbox`. For installs, restarts, pushes and API smoke tests, hand Scott the exact NUC terminal command.
- After a push to the Hermes Dropbox mirror, give Scott:
  `find ~/Dropbox/hermes-mirror.git \( -name '*.lock' -o -name '*.keep' -o -name 'incoming-*' \) -exec rm -rf {} +`

### 0.6 Accuracy
- **Flag uncertainty; never guess.** This covers model IDs, package names, versions, ports, API endpoints and prices.
- Verify by **running** (tests, a browser check on a phone viewport), not by reading code.
- Never print key values.

### 0.7 Rules that carry over from existing systems
- **ProReady:**
  - Nothing AI-generated reaches study screens without **admin review**.
  - Students see no AI branding.
  - Full edit history with revert.
  - `tenantId` on new models.
  - Fields stay **strictly separated**.
  - Text stays scientifically rigorous.
- **CompTIA content:**
  - Verify the **current official exam code and objectives**. Prioritize high-weight and new or changed topics, and call them out.
  - State the exam code used. **Security+ defaults to SY0-801.**
- **Hermes:**
  - Everything is built **toward the portfolio**, through one **review space** where Scott approves before anything publishes.
  - **Build-and-learn:** Claude builds with Hermes, fills the gaps, then teaches Hermes to do it next time.
  - New capabilities arrive **sandboxed and labeled "Experimental"**. Never block Scott.
- **AI Lab:**
  - Reuse the **Night/Day Shift model router and budget guard**. Don't build a second one.
  - Generated code runs in a **container sandbox**.
- **Privacy:** no ERASMUS, account or personal data goes to hosted models.
- **Monitors:** any new signal or monitor must **cause changes**, shadow-first and armed by Scott, not just display a number.

---

## 1. Model plan (cost control)

**Principle:** use the cheapest model that can do the phase well. Escalate only on failure, and drop back down afterwards.

### 1.1 Tiers
- **Fable** handles heavy design, novel architecture and the hardest debugging. It's the most expensive, so use it in short bursts.
- **Opus** handles complex multi-file builds, safety-critical logic and game builds.
- **Sonnet** handles audits, routine builds, pipelines, bulk content and tests.
- **Haiku** handles bulk tagging, alt-text drafts, metadata, license-field checks and simple classification inside Hermes jobs.

⚠️ **Verify at Phase 0:** the current model lineup and exact IDs. As of this writing they're believed to be `claude-fable-5-2`, `claude-opus-5-5`, `claude-sonnet-5-5` and `claude-haiku-5-5`. Model IDs come from **env vars** in the shared router and are never hard-coded.

### 1.2 Per-phase assignment
- **Phase 0 (audit):** Sonnet
- **Phase 1 (architecture and motion design):** Fable
- **Phase 2 (shared spine):** Opus
- **Phase 3 (AI Lab generation side):** Opus
- **Phase 4 (Hermes scavenger and editor side):** Sonnet
- **Phase 5 (project connectors):** Opus, because of the ERASMUS safety logic
- **Phase 6 (ProReady motion engine):** Opus, with Fable for one design review at the start if Phase 1's motion spec has open questions
- **Phase 7 (IT visuals for cards and quizzes):** Sonnet. Hermes jobs inside it use Haiku for tagging.
- **Phase 8 (interactive effects across cards, quizzes and games):** Opus
- **Phase 9 (game assets):** Opus. Fable designs the games and Claude decides them; Scott delegated game design.
- **Phase 10 (learning-loop tuning and final verification):** Sonnet. An independent Opus reviewer that hasn't seen the build does the final check.

### 1.3 Switching and escalation rules
- **Session model:** each phase report ends with "Next phase model: X". Scott switches with `/model` or the Cowork picker before replying "go". If the running model doesn't match the phase, say so in one line and wait.
- **Escalate:**
  - Sonnet → Opus after **2 failed attempts** at the same fix.
  - Opus → Fable after 2 more failures, or when a design question has no clear answer.
  - Report every escalation in one line.
- **De-escalate:** go back to the phase's assigned model as soon as the blocker clears.
- **Bulk work:** non-urgent bulk generation (alt text, tags, question-image pairing) runs **overnight through Night Shift** using the **Message Batches API** where the router supports it.
  - ⚠️ The batch discount is believed to be about 50%. Verify current pricing.
- **Image and video generation** costs are separate from Claude. Show an estimated cost per job before it runs (see §3.4).

---

## 2. What's being built (locked decisions, 2026-11-25)

### 2.1 The loop
- The **AI Lab** is the creative side. It generates images, video, 3D animation and motion, and designs interactive features like tap ripples.
- **Hermes** is the cheap side. It edits existing assets, pulls material from the internet, and handles conversions and cleanup.
- Work goes **back and forth** between the two, each learning from and building on the other's output. Finished output flows into **ProReady**, and later into any connected project.

### 2.2 Routing is goal-based
- Scott describes the **project and its goal** in the AI Lab.
- A planner splits the goal into pieces. Each piece goes to whichever side does that kind of job best, **in either direction**. For example, Hermes finds a base diagram, the AI Lab animates it, then Hermes compresses it for offline use.

### 2.3 Learning
- **Both** signals steer routing:
  - A **shared recipe log**, recording what worked, its cost, its quality, which side did it, time taken and failures.
  - **Scott's ratings** of outputs.

### 2.4 Licensing for pulled material
- **Mode A (standard):** anything goes for personal use, with the asset **flagged "personal-use"**.
- **Mode B (option, per job or per asset):** pulled material is **reference only**, and the AI Lab recreates it as an original.
- **Guard:** a personal-use asset is **blocked** from the portfolio, any sold or client version of ProReady, and any public demo (including Cloudflare-tunnel demos) until it's recreated (Mode B) or cleared with a verified open license.
- **ProReady is personal for now** (no students or clients), so personal-use assets may appear in Scott's own study screens. The moment a field gets a student, client or sale, its personal-use assets are hidden and queued for recreation. The Copyright Guardian must treat the "personal-use" tag this way and not hard-block it at ingest; flag it if its current logic conflicts.
- **Pull etiquette:** respect robots.txt and site terms, and never pull from behind paywalls or logins.
- Openly licensed or public-domain finds are tagged as such and pass the guard, but only after the **existing TASL attribution and Copyright Guardian** checks.

⚠️ **Flag for Scott:** in voice he said "two and three… both standard and the option". This prompt reads that as Mode A standard and Mode B as the option. Confirm at the Phase 1 gate.

### 2.5 Delivery into ProReady
- Assets land as **drafts in ProReady's admin review**. Scott approves them before they appear in study screens.

### 2.6 Project connectors
- Both the AI Lab and Hermes get connectors so they can **push updates into any connected project**.
- **ERASMUS:**
  - **Read-only and suggestion-only** until **2027-01-01**.
  - From then on it gets full push access, but every push still follows ERASMUS's **shadow-first rule** (nothing goes live until Scott arms it), its build freeze and its own gates.

### 2.7 Scope order
- **Every part of the system goes in, phased:**
  - Quiz and flashcard visuals
  - Interactive UI effects
  - Game assets
- **The first job** is the IT study material in ProReady.

### 2.8 Hands-off rule (Scott, 2026-11-25) — applies to every phase
- **Goal:** Scott no longer does anything by hand in Hermes. The **AI Lab drives everything**: it presses every button, pushes every project and makes every change, through Hermes tools.
- **Coverage it must reach (not only ProReady):**
  - **ProReady:** create and update fields, cards, quizzes and games.
  - **Portfolio:** upgrade and publish **scottchristensen.dev** (Hermes Site Studio, `workshop/sitestudio/static_sites.py`).
  - **Photos and video people send him:** take them from intake (Iris, Drop, Inbox), then edit them with every Hermes editor (Image Studio, the video and media studio, ComfyUI pictures) and hand back the result.
  - **Business systems:** build workflows for Scott and for clients in the Automation Studio (`forge/automation`), including the GPT builder.
  - **Every other studio** as it gets an MCP tool.
- **How:** every studio action gets an **MCP tool** on the Hermes server (preferred). Where a tool doesn't exist yet, the Lab may drive the studio's own UI through Hermes's hidden browser, and the gap is logged so a real tool gets built (build-and-learn).
- **Still gated, even hands-off:** anything that publishes publicly, sends to a client or another person, spends money above the per-job threshold, deletes, or touches ERASMUS. These land in the one **review space** as a single tap for Scott. Everything else runs on its own.
- **Trust toggles (Scott, 2026-11-25):** a **Settings → Trusted tasks** menu lists each gated task type (e.g. "publish portfolio page", "send workflow to client X", "jobs under $Y"). Each has a toggle, off by default. Turning one on lets that task run without the tap. Scott adds trusted tasks over time.
  - Each toggle can be narrowed by project, client or cost cap.
  - Every auto-run trusted task still logs to the review space as "done on trust", with undo where possible.
  - **ERASMUS live arming and deletes can never be trusted.** Those toggles don't exist.
- **Other people's photos and client data** follow the Hermes Security Layer: client scoping, offshore flags, never sent to providers that train on prompts.

---

## 3. Design requirements

### 3.1 Tactile visuals for ProReady (the first job's goal)
- **The feel:** tap the screen and something physical happens.
  - Current flows through a circuit.
  - Packets travel a network.
  - A drive head seeks.
  - A permission bit flips.
  - Malware spreads, and a firewall rule stops it.
- The reference is a sonogram demo that shows **vibrations moving through tissue**: the motion **is** the lesson, not decoration.
- **Code-rendered first:**
  - Most interactive motion should be **SVG, Canvas or WebGL with CSS or JS animation**, not generated video.
  - That keeps it cheap, interactive, small and **usable offline**.
  - Generated images or video are for things code can't draw well, such as photo-real hardware or textures.
- **Haptics:**
  - `navigator.vibrate()` works on Chromium browsers on Android, which covers Scott's phone. Firefox removed it, and iOS Safari has never supported it.
  - Feature-detect it, and make each effect work without it (visual plus an optional sound cue).
  - Vibration only fires from a user gesture.
- **Settings:** motion on/reduced/off (respect `prefers-reduced-motion`), haptics on/off and sound on/off. Store them per user.
- **Readability:** follow ProReady's existing large-text, high-contrast and night-mode settings. No neon. Motion must never hide the text being studied.
- **Performance:**
  - Target **60 fps on a mid-range Android**, and degrade gracefully.
  - Pause animations off-screen and when the tab is hidden.
  - Set a per-effect budget for size and CPU, and measure it.
- **Offline:** every asset and effect used by the A+, Linux+ and Security+ offline modes gets cached with the existing offline bundle. Verify in airplane mode.

### 3.2 Motion primitive library
- Build **reusable primitives**, not one-offs. Phase 1 finalizes the list. Seed list:
  - Tap ripple
  - Current flow along a path
  - Packet travel with hops
  - Wave propagation and attenuation
  - Layer stack peel (OSI and TCP/IP)
  - Toggle and bit flip
  - Fill and drain gauges (CPU, RAM, disk)
  - Heat and airflow
  - Process tree expand
  - Encrypt and decrypt scramble
  - Lock and shield block
  - Pulse feedback for right and wrong answers
- Each primitive is **data-driven**: a card or quiz references a primitive plus parameters. That lets Hermes and the AI Lab compose new visuals without new code.
- Primitives live in ProReady and are **field-agnostic**, so sonography and other fields can use them later.
- **3D motion:** where depth helps (inside a PC case, a drive platter, a server rack), use code-rendered 3D (Three.js/WebGL, glTF models) under the same primitive format. Each has a 2D fallback for reduced-motion and low-end devices. ⚠️ Confirm the library choice against ProReady's existing dependencies in Phase 0.

### 3.3 Job spec (shared by both sides)
- **Fields:**
  - Goal
  - Target project and field
  - Asset type
  - License mode
  - Quality bar
  - Budget cap
  - Deadline or priority
  - Offline needed?
- The planner fills in the pieces, the chosen side, the reason and the estimated cost.
- Every piece writes a **recipe log entry** when it finishes.

### 3.4 Cost guard
- Reuse the shared **budget guard**: daily caps there, plus monthly caps set in each provider's dashboard. Give Scott those steps.
- **Estimate before generating:** each AI Lab image or video job shows its estimated cost.
  - Jobs over a per-job threshold wait for Scott. Phase 1 proposes the threshold, and Scott sets it.
  - Below the threshold, jobs run inside the daily cap.
- **Hermes first** when the recipe log says the cheap side can meet the quality bar.

### 3.5 Generation access (AI Lab)
- **Model access** is a mix, all wired from the start: the OpenRouter gateway, direct Claude keys and Hugging Face.
- **OpenRouter:**
  - Images run through `POST /api/v1/images`.
  - Video is **asynchronous** through `POST /api/v1/videos`, with polling.
  - Discover models through `GET /api/v1/images/models` and `GET /api/v1/videos/models`.
  - ⚠️ Confirm the endpoints and current model list at build time. **Never hard-code model names.**
- **Local generation** is gated by Hermes hardware detection. gandalf has 16 GB of RAM and no big GPU, so most generation is cloud-based for now. Light up local options automatically on the future workstation.

---

## 4. Phases

> Each phase ends with a short report, a handoff file and a gate.

### Phase 0 — Read-only audit · **Sonnet**
Change nothing. Report what exists and its condition.
1. **Repos:** locate Hermes and ProReady, confirm the live ProReady copy, and read each repo's `CLAUDE.md`, ledger and `DECISIONS.md`.
2. **AI Lab Studio:**
   - Does any part of it exist (router hookup, live preview, agent loop)?
   - Look for `HERMES_AI_LAB_STUDIO_FINAL.md` and any AI Lab build prompt.
3. **Night/Day Shift:** the router, budget guard, model env vars and whether batch is supported.
4. **Hermes:**
   - Image Studio, 3D Print Studio, Add-on Studio and Web Harvest
   - Any editing tools installed (ImageMagick, ffmpeg, SVG tools, background removal)
   - The review space and the portfolio site module
5. **ProReady:**
   - Admin review queue and draft flow
   - TASL attribution and Copyright Guardian
   - Offline bundle and caching
   - Card, quiz and game renderers, and the Linux+ fake terminal
   - Current A+, Linux+ and Security+ content counts and exam codes
   - Any existing animation or haptics code
6. **Connectors:** any existing cross-project push mechanism, and how ERASMUS's shadow-first arming works.
7. **Models:** the current Claude lineup and IDs, plus OpenRouter image and video availability. Hand Scott the curl commands; the shell has no network.

**Report:** a list of what exists, what's missing and what's broken. Recommend what to **reuse** and what to build.

**Gate:** "Proceed to Phase 1? (model: Fable)"

### Phase 0 findings (2026-11-25) — what later phases build on
- **AI Lab is already built** (~/ailab, 565 tests): provider layer, router chat, live preview, agent loop, compare, review, pictures, video, cast, styles, shelf/library, eyes (local vision check). Phases 2–3 **extend it, they don't rebuild it**. Skip the "AI Lab core" steps.
- **Hermes MCP server** exposes ~30 tools to the Lab (llm_call, spend_*, review_*, recipes_search, lessons_search, jobs_*, linux_app_*, addon_build, app_ship, mario_*, pidima_*, cast_*). **No tools yet** for Image Studio edits, media/video studio, Site Studio/portfolio publish, Automation workflows, intake, or ProReady. That gap is the core of §2.8.
- **Recipe log:** `recipes_search` / `lessons_search` already exist. Extend them with cost, quality, side and ratings instead of a new log.
- **Night/Day Shift:** `forge/night` has routing, day, learn, lessons and review. Reuse its router and budget guard.
- **ProReady:** live in `~/SonoVault` (Next 16.4, Prisma 7.10). It has a copyright/attribution panel, an offline store (`src/lib/offline`, `RegisterLabOffline`), lab components (Terminal, PermissionPuzzle, ControlSort and others), and `navigator.vibrate` already in `src/components/lab/ui.tsx`. **No motion or 3D library** is installed yet.
- **Concurrency:** another session committed to ~/ailab this morning, and ~/hermes has 111 uncommitted files. Use a private `GIT_INDEX_FILE` and stage named paths only (ledger rule A4).

### Phase 1 — Architecture and motion design · **Fable**
1. Design the **shared spine**:
   - Job spec schema
   - Goal planner
   - Router (rules plus recipe-log scoring plus ratings)
   - Recipe log schema
   - Rating UI
   - License-mode tagging and the portfolio and sale guard
   - Cost estimator
   - Trusted-tasks settings menu (§2.8): task-type list, toggles, scoping, "done on trust" log
2. Design the **connector contract**:
   - Push = proposed change, then the target project's own review or draft flow.
   - The ERASMUS date gate.
3. Finalize the **motion primitive library** (§3.2) and its parameter format. Map the top IT topics to primitives, by exam weight.
4. **Operator layer (§2.8):** list every studio action Scott does by hand today, and give each one an MCP tool spec (or a hidden-browser fallback). Order them: ProReady, then portfolio, then photo/video intake and editing, then Automation workflows, then the rest.
5. Propose the per-job cost threshold.
6. List any open questions as **one numbered menu**, with a recommendation each. Include the license-mode confirmation from §2.4.

**Output:** `docs/CREATIVE_LOOP_DESIGN.md` in Hermes, plus a short outline in chat.

**Gate:** **"Would you like me to proceed with the final build based on this outline?"**

### Phase 2 — Shared spine · **Opus**
- Build the job spec, planner, router, recipe log, ratings store and cost estimator.
- Wire them to the **existing** budget guard and model router.
- Put the review space hookup in place.
- **Tests:**
  - Routing picks Hermes when the log shows it meets the bar.
  - Budget caps block jobs.
  - Personal-use assets can't reach the portfolio.

**Gate:** "Proceed to Phase 3? (model: Opus)"

### Phase 3 — AI Lab generation side · **Opus**
- Extend the existing Lab (don't rebuild it). Add the new MCP tools from the Phase 1 operator list, the first batch on this phase and the rest in Phase 5.
- **Adapters:**
  - Image generation and editing
  - Async video generation with polling
  - Motion and interaction authoring: the AI Lab writes primitive parameters and code-rendered effects, previewed live
  - 3D assets and motion: glTF models from open sources (via Hermes) or generated, with heavy local 3D generation gated to future hardware
- **Rating buttons** sit on every output in the live preview and the review space, and feed the ratings store.
- Mode B **recreate-from-reference** flow.
- **Tests:** mock providers, plus one real low-cost image job run by Scott from the terminal.

**Gate:** "Proceed to Phase 4? (model: Sonnet)"

### Phase 4 — Hermes scavenger and editor side · **Sonnet**
- **Search adapters:** start with open sources (Openverse, Wikimedia Commons, NASA, government sites). General web pulls are allowed under Mode A and tagged personal-use.
- Capture the source URL and any license data for every pull.
- **Edit pipeline:** crop, resize, recolor to the ProReady palette, label overlays, SVG optimize, ffmpeg trim and compress, and an offline-size budget.
- **Haiku** handles tagging and alt-text drafts.
- **Tests:** a round trip where Hermes pulls a diagram, the AI Lab animates it and Hermes compresses it. Every step logs.

**Gate:** "Proceed to Phase 5? (model: Opus)"

### Phase 5 — Project connectors · **Opus**
- **ProReady connector:** push into the **admin review drafts**, never straight to students.
- **Generic connector** for other projects. Each project declares its own review or draft target.
- **Operator tools, batch 2:** Site Studio publish for scottchristensen.dev (gated in the review space), photo/video intake to the editors and back, and Automation workflow create/run for Scott and clients (client sends gated).
- **ERASMUS connector:**
  - Read-only and suggestions only until `2027-01-01T00:00` Pacific.
  - On that date, push unlocks automatically, and **Bell** sends Scott a silent notification.
  - Every push lands **in shadow**, never live, and respects any active build freeze. Arming stays manual.
- **Tests:**
  - Date-gate tests with a mocked clock: before, at and after the switch.
  - A shadow-only test.

- **No night tail for this phase.** ERASMUS work is never run overnight unattended.

**Gate:** "Proceed to Phase 6? (model: Opus)"

### Phase 6 — ProReady motion engine · **Opus**
- Build the primitive library from Phase 1, plus the settings (motion, haptics, sound) and the offline caching hook.
- Add a **demo page** in admin showing every primitive with live parameter sliders.
- **Measure:** fps on a mid-range Android profile, bundle size, and an airplane-mode check.
- Hand Scott a test checklist for his phone.

**Gate:** "Proceed to Phase 7? (model: Sonnet)"

### Phase 7 — First job, part A: IT visuals for cards and quizzes · **Sonnet**
- Order: **A+**, then **Linux+**, then **Security+ (SY0-801 unless Scott says otherwise)**.
- Within each, work by **exam weight**, highest first, calling out new or changed objectives.
- Route each visual through the loop. Prefer a primitive or code-rendered diagram, then a Hermes pull and edit, then AI Lab generation, as the recipe log advises.
- Every asset becomes an **admin review draft** with TASL data and a license-mode tag.
- Bulk runs go overnight through Night Shift where possible.

**Report:** counts per field and objective, cost spent and the review queue size.

**Gate:** "Proceed to Phase 8? (model: Opus)"

### Phase 8 — First job, part B: interactive effects · **Opus**
- Wire primitives into flashcards (tap to reveal with motion), quizzes (right and wrong feedback, and visual explanations that animate the concept) and existing games, across all three IT fields.
- Respect the settings and offline mode.

**Gate:** "Proceed to Phase 9? (model: Opus)"

### Phase 9 — First job, part C: game assets · **Opus (Fable for game design)**
- **Linux+:**
  - Fake-terminal labs get visual consequences: files appear, permissions change colour, services start with current-flow animation.
  - Bash and Python code-reading tie-ins.
- **A+ and Security+:** game assets built from the same primitives.
- Claude designs the games without asking Scott about game design, and makes them well.

**Gate:** "Proceed to Phase 10? (model: Sonnet)"

### Phase 10 — Learning-loop tuning and verification · **Sonnet, plus an independent Opus reviewer**
- Tune router weights from the recipe log and ratings, and report what changed and why.
- Make sure Hermes has learned the recurring recipes (build-and-learn).
- **Independent reviewer:** a fresh Opus agent that didn't build this checks the system against §2 and §3, runs the tests and does a phone-viewport browser check.
- Update ProReady's in-app manual and the Hermes briefing.
- **Final handoff:** what's live, what's in review, cost totals and the next suggested job.

---

## 5. Acceptance (whole build)
- [ ] One goal typed into the AI Lab produces routed pieces on both sides, a round trip, recipe-log entries and an admin draft in ProReady.
- [ ] Personal-use assets are provably blocked from the portfolio, sold versions and public demos.
- [ ] The ERASMUS connector is read-only before 2027-01-01, pushes to shadow after, and never goes live without arming.
- [ ] Every IT field has tactile visuals and effects in cards, quizzes and games, working offline, at a measured 60 fps target, with haptics on Android.
- [ ] Costs stayed inside the budget guard, and each phase ran on its assigned model, with escalations reported.
- [ ] All AI output passed admin review before reaching study screens.
- [ ] Scott can give the AI Lab a goal for ProReady, the portfolio, a sent photo or a client workflow, and it finishes the job through Hermes tools with no manual Hermes clicks. The only taps are the gated ones in the review space.

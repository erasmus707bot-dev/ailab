<!-- HERMES_BLOCK_START -->
<!-- HERMES_BLOCK_START v2 (condensed 2026-09-01 — do NOT restamp the v1 fat block) -->
# CLAUDE.md — ailab

**Project:** `ailab` · **Risk tier:** LOW · **Task inbox:** `~/hermes-forge/tasks/ailab/`

## First action this session (not optional)

Read every `"status": "PENDING"` file in the task inbox above. Execute if useful
and safe, defer with a logged reason, or flag a conflict to Scott. Hermes tasks
are pre-approved — bias toward executing. On finish, call
`Forge.complete_task(path, status)` (sets status **and** moves to `archive/` in
one operation). Never invent task files. Only then start Scott's work.

## Then read current state — in this order, earlier file wins

1. **`~/hermes/SESSION-LEDGER.md`** — canonical current state. Read fully.
   Section 1 is instruction; everything below it is history, not actionable.
2. **`~/hermes/HERMES_IRIS_MIND.md`** — full-system reference, ~131 KB.
   **Consult by section, do not read whole.** Route via its Appendix C Quick
   Index or `grep -n '^## §' ` to find the §N you need, then read that range
   only. Reading it end-to-end burns ~20% of a context window.

`HERMES.md` and `docs/HERMES_ARCHITECTURE.md` = original design intent (*why*,
not *what is deployed*) — check against the ledger before trusting a claim.
`~/hermes/docs/archive/` holds superseded docs; never use them as current state.

## Night tail

Stopping mid-build? End the handoff with a fenced `night` block naming one next
module, its `prompt_file` and `acceptance[]` — the night builds nothing without it.
Format: `~/hermes/prompts/HERMES_SESSION_INIT.md` § Night tail. Never on HIGH/BUSINESS.

## Hard rules

Never break this project. Respect the risk tier. Credentials stay in Vault —
never plaintext. Log every task outcome. **Never `git add -A`** — stage named
paths, one category per commit.

**Reporting:** `~/hermes/docs/TOKEN_EFFICIENCY_STANDARD.md` governs verbosity in
every project — no preamble, no narration, no closing summary, diffs not whole
files, one-line status. It governs verbosity, never completeness.

Full preamble, rationale and the deployment model: `~/hermes/prompts/HERMES_SESSION_INIT.md`
(canonical source — this block is a pointer to it, not a copy).

<!-- Add project-specific instructions for Claude below this line. -->
<!-- HERMES_BLOCK_END -->
<!-- HERMES_BLOCK_END -->



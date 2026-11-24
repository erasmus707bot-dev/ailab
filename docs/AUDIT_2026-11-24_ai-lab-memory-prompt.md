# AUDIT 2026-11-24 — AI Lab memory import + prompt builder (Module 0, read-only)

Prompt: `~/hermes/prompts/BUILD_PROMPT_2026-11-24_ai-lab-memory-prompt-builder.md`

## Live state (Lab restarted 05:5x)
- connected · flags router/preview/agent/compare/live on · 0 runs.
- Keys in Hermes: openrouter ✅ · qwen ✅ (qwen-plus) · kimi ✅ (kimi-k3, kimi-k3.1-pro) · claude ✅ · hf ✗.
- Ollama on gandalf: qwen3.5:4b, qwen3.5:9b, nomic-embed-text only (dolphin3/llama3.1 no longer installed).
- Robot fix live-proven: robot on #scan → Hermes `scan-status.started` unchanged (13:37Z) = the real page was NOT clicked.
  The live run exposed a false 🔴 (404 polls after New's blocked save) → fixed `0c38373` (load-time 404 still red). 148 tests OK. Loads at next restart.

## What exists vs needed
| Need | Exists? |
|---|---|
| Lab memory store | ✗ none (store.py = projects + autosave only) |
| Agent context from memory | ✗ (agent.py has no memory/profile input) |
| Sensitive filter | ✓ `secretscan.py` (keys) + `privacy.py` — no health/finance/identity rules yet |
| Hermes MCP memory / notify / queue tools | ✗ none in `forge/projects/mcp_server.py` TOOLS (41 tools: jobs, spend, llm_call, review, pidima, mario, linux_app) |
| Iris "finished/stuck" | partial — Lab `/api/state runs[]` has state/stuck/proved; nothing pushes it to Iris yet |
| Big-job queue | ✓ `~/hermes-forge/day/orders/*.json` (status queued, priority) read by `forge/night/day.py` |
| Build view / pop-ups | partial — run view + approvals exist; no done/doing/left list |

## Import sources
- On gandalf, readable now: `~/ailab/CLAUDE.md`, `~/hermes/CLAUDE.md`, `~/hermes-local/CLAUDE.md`, `SESSION-LEDGER.md` §1 (575 lines total; §1 only).
- `~/.claude/` (Claude Code CLAUDE.md, skills like scott-conventions): NOT in this session's folders — the Lab reads it itself at runtime on gandalf. UNVERIFIED contents.
- **Claude.ai memory (profile/preferences/areas/people) is NOT on gandalf** — it lives in claude.ai. Path: Claude writes a one-time export `.md` into `~/hermes-data/claude-memory-export/`, the Lab imports that; re-export on request. Sensitive lines (health, identity) are dropped at export, not just at import.
- No `rules.md` found in connected folders.

## Gate 0 picks (defaults unless Scott changes)
1. Memory store → Lab-own `~/.config/ailab/memory/`.
2. Big jobs → Day/Night order file in `~/hermes-forge/day/orders/` + 📋 copy box.
3. Re-import → 🔄 button + nightly "your Claude setup changed — review?".

## Added scope: 🎨 "fewer limits" label (Scott 2026-11-24)
New per-model tag `limits`: 🎨 fewer limits · ⚖️ normal · 🔒 strict (provider filters). Plus a ⭐ list filter "🎨 only".
Proposed tags (sources: morphllm Nov 2026, atlascloud/featherless 2026 guides — UNVERIFIED until a Compare probe):
- 🎨 hosted: `nousresearch/hermes-4-405b` (neutral alignment, $1/$3, OpenRouter) · `venice/uncensored` (chat/creative, no tool calling — never `:free`, it logs prompts).
- 🎨 local (pull needed): `dolphin3:8b`, `hermes3:8b` (fit the 6 GB card).
- ⚖️ deepseek, glm, minimax, inkling (open weights, moderate) · 🔒 qwen direct, kimi direct, claude (provider-side filters).
- Privacy note: qwen/kimi **direct** keys go straight to Alibaba/Moonshot — no OpenRouter ZDR routing. Lab should show that on the Keys page. UNVERIFIED whether Hermes llm_call applies any guard on those.
- Images: the Lab is text/code. Image art = Hermes Image Studio; open local options that fit 6 GB: SDXL/Juggernaut XL, Z-Image (6B, Apache 2.0). FLUX.2 dev has a built-in filter; FLUX.1 dev does not. Proposed: same 🎨 tag on Image Studio models — separate small build.
- Hard line stays regardless of model: nothing sexual involving minors, no real people's likeness without consent.

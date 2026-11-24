# HANDOFF 2026-11-24 — AI Lab keys check: robot live proof, 🧪 provider Test, 💎 Gemini in the Lab

## Live proofs (Claude in Scott's Chrome)
- **Robot never clicks the real page** (fix f3094fc/0c38373): Show & change on Hermes home, selector `#scan`, no change asked.
  Robot clicked New only ("the test copy blocked it"); real Hermes `/api/scan-status` stayed idle/never started. 🔴 "looks the same" = expected (no change). Shots `20261124-062743-{now,new}.png`.
- **🧪 Test on Gemini**: ✅ 65 models · default `gemini-3.8-flash` ✓ · heavy `gemini-4-argon` ✓ (free, no chat call).
- **Lab sees Gemini**: /api/keys gemini 💎 listed+set; /api/models?provider=gemini → both models.

## Commits
- ~/hermes `5d9cb967` providers.test_provider + POST /api/provider-test (owner-only, audited, key never returned) +4 tests
- ~/hermes `9a01f1f4` Settings → API Keys: 🧪 Test button per provider (count, ✓/✗, near names)
- ~/hermes `de7b0fbc` config: kimi direct off (keys check) + gemini use_for ailab. NOTE: also carries
  `cloud_default_provider: openrouter` (was claude) — that was already uncommitted, not set by this session; Scott to confirm.
- ~/ailab `df3db8e` 💎 Gemini provider, 🔒 strict, +2 tests (174 OK); UI warning line landed in `762fd69`.

## Not done
- No real Gemini chat call from the Lab yet (cents). Gemini goes direct to Google, not the ZDR OpenRouter route.
- Phone-width touch test of the 🧪 button (Argus) owed.

Continue: `continue AI Lab memory + prompt builder from the 2026-11-24 handoff`

"""2026-11-24: Gemini is a Lab provider (key held by Hermes in connected mode), tagged 🔒 strict."""
import unittest

from ailab import providers, roster
from ailab.keys import ENV_NAMES
from ailab.server import PROVIDER_ICONS


class Gemini(unittest.TestCase):
    def test_gemini_is_built_with_google_openai_endpoint(self):
        ps = providers.build({}, transport=None)
        g = ps["gemini"]
        self.assertEqual(g.base_url, "https://generativelanguage.googleapis.com/v1beta/openai")
        self.assertEqual(g.key_name, "gemini")
        self.assertFalse(g.local)
        self.assertEqual(g.extra_body(), {})            # no OpenRouter ZDR body sent to Google

    def test_key_env_icon_and_strict(self):
        self.assertEqual(ENV_NAMES["gemini"], "GEMINI_API_KEY")
        self.assertEqual(PROVIDER_ICONS["gemini"], "💎")
        self.assertEqual(roster.limits_tag("gemini", "gemini-3.8-flash"), roster.limits_tag("claude", "claude-sonnet-5-5"))


if __name__ == "__main__":
    unittest.main()

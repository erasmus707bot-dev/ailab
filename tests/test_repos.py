"""🔗 Linked code folders (workbench M5): read rules, pull, and propose-only."""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from ailab import agent, repos


class Repos(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name).resolve()
        self.repo = self.home / "hermes"
        (self.repo / "forge").mkdir(parents=True)
        (self.repo / ".git").mkdir()
        (self.repo / "node_modules" / "x").mkdir(parents=True)
        (self.repo / "forge" / "card.py").write_text("def status():\n    return 1\n")
        (self.repo / "forge" / "keys.py").write_text('TOKEN = "sk-ant-api03-' + "a" * 40 + '"\n')
        (self.repo / ".env").write_text("X=1")
        (self.repo / ".git" / "config").write_text("def status")
        (self.repo / "node_modules" / "x" / "i.js").write_text("def status")
        (self.repo / "data.db").write_text("def status")
        (self.home / "outside.txt").write_text("def status")
        os.symlink(self.home / "outside.txt", self.repo / "forge" / "link.py")
        self.proj = self.home / "proj"
        self.proj.mkdir()
        p = mock.patch.object(Path, "home", return_value=self.home)
        p.start()
        self.addCleanup(p.stop)
        self.addCleanup(self.tmp.cleanup)
        self.cfg = {"repos": {"hermes": str(self.repo), "Bad Name": str(self.repo), "gone": str(self.home / "nope"),
                              "dot": str(self.repo / ".git")}}

    def test_only_real_named_folders_link(self):
        self.assertEqual(list(repos.linked(self.cfg)), ["hermes"])
        with self.assertRaises(repos.RepoError):
            repos.root_of(self.cfg, "gone")

    def test_programs_group_only_linked_folders(self):
        forge = self.home / "hermes-forge"
        forge.mkdir()
        cfg = {**self.cfg, "repos": {**self.cfg["repos"], "hermes-forge": str(forge)},
               "programs": {"hermes": ["hermes", "hermes-forge", "gone", "hermes"], "empty": ["gone"], "Bad Name": ["hermes"],
                            "odd": "hermes"}}
        self.assertEqual(repos.programs(cfg), {"hermes": ["hermes", "hermes-forge"]})
        self.assertEqual(repos.programs(self.cfg), {})

    def test_token_files_are_never_read(self):
        (self.repo / "forge" / "tokens").mkdir()
        (self.repo / "forge" / "tokens" / "x.py").write_text("def status")
        (self.repo / "forge" / "ailab.token").write_text("def status")
        (self.repo / "forge" / "tokens.json").write_text("def status")
        for bad in ("forge/tokens/x.py", "forge/ailab.token", "forge/tokens.json"):
            with self.assertRaises(repos.RepoError, msg=bad):
                repos.read_text(self.repo, bad)
        self.assertEqual({m["path"] for m in repos.find(self.repo, "def status")["matches"]}, {"forge/card.py"})

    def test_find_skips_hidden_vendored_linked_and_secret_files(self):
        r = repos.find(self.repo, "def status|TOKEN")
        self.assertEqual({m["path"] for m in r["matches"]}, {"forge/card.py"})
        self.assertEqual(repos.find(self.repo, "def status", glob="*.js")["matches"], [])

    def test_list_hides_what_is_never_read(self):
        r = repos.ls(self.repo)
        self.assertEqual(r["dirs"], ["forge/"])
        self.assertEqual(r["files"], [])
        self.assertEqual([f["path"] for f in repos.ls(self.repo, "forge")["files"]], ["forge/card.py", "forge/keys.py"])

    def test_safe_refuses_escapes(self):
        for bad in ("../outside.txt", "/etc/passwd", ".env", ".git/config", "node_modules/x/i.js", "data.db",
                    "forge/link.py", "forge/../../outside.txt", ""):
            with self.assertRaises(repos.RepoError, msg=bad):
                repos.read_text(self.repo, bad)

    def test_pull_copies_names_only_and_refuses_secrets(self):
        r = repos.pull(self.repo, "hermes", ["forge/card.py", "forge/keys.py", ".env"], self.proj)
        self.assertEqual(r["copied"], ["repos/hermes/forge/card.py"])
        self.assertEqual(len(r["refused"]), 2)
        self.assertNotIn("return 1", str(r))                               # text went to disk, not into the reply
        self.assertTrue((self.proj / "repos/hermes/forge/card.py").is_file())
        self.assertFalse((self.proj / "repos/hermes/forge/keys.py").exists())

    def _run(self):
        r = agent.Run.__new__(agent.Run)
        r.cfg, r.root, r.project, r.id, r.is_lane = self.cfg, self.proj, {"id": "scratch"}, "run1", False
        return r

    def test_propose_holds_and_never_writes_the_real_folder(self):
        held = []
        with mock.patch.object(agent, "hold_for_approval", side_effect=lambda *a, **k: held.append((a, k)) or {"id": "A1"}), \
             mock.patch.object(agent, "approvals", return_value=[]):
            r = self._run()
            r._repo({"repo": "hermes", "do": "pull", "paths": ["forge/card.py"]})
            same = r._repo({"repo": "hermes", "do": "propose", "paths": ["forge/card.py"]})
            self.assertEqual(same["proposed"], [])                          # unchanged copy: nothing to propose
            (self.proj / "repos/hermes/forge/card.py").write_text("def status():\n    return 2\n")
            (self.proj / "repos/hermes/forge/new.py").write_text("x = 1\n")
            out = r._repo({"repo": "hermes", "do": "propose", "note": "two",
                           "paths": ["repos/hermes/forge/card.py", "forge/new.py", ".env", "forge/missing.py"]})
        self.assertEqual([p["path"] for p in out["proposed"]], ["forge/card.py", "forge/new.py"])
        self.assertEqual(len(out["skipped"]), 2)
        self.assertEqual(held[0][0][2], str(self.repo / "forge" / "card.py"))
        self.assertEqual((self.repo / "forge" / "card.py").read_text(), "def status():\n    return 1\n")   # untouched
        self.assertFalse((self.repo / "forge" / "new.py").exists())

    def test_compare_lanes_cannot_propose_and_unknown_folder_is_an_error(self):
        r = self._run()
        r.is_lane = True
        self.assertIn("error", r._repo({"repo": "hermes", "do": "propose", "paths": ["forge/card.py"]}))
        self.assertIn("error", self._run()._repo({"repo": "nope", "do": "find", "pattern": "x"}))

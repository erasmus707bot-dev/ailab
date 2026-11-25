"""📍 Visible project folders + Where panel (2026-11-24)."""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from ailab import config, preview


class Where(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["AILAB_HOME"] = self.tmp.name

    def tearDown(self):
        os.environ.pop("AILAB_HOME", None)
        self.tmp.cleanup()

    def test_new_project_lives_in_visible_folder_with_pictures_and_docs(self):
        d = preview.ensure_site("fresh")
        self.assertEqual(d, config.files_home() / "fresh")
        self.assertTrue((d / "index.html").is_file() and (d / "pictures").is_dir() and (d / "docs").is_dir())

    def test_old_hidden_project_is_copied_and_old_kept(self):
        old = preview.legacy_site_dir("oldie")
        (old / "pictures").mkdir(parents=True)
        (old / "index.html").write_text("<h1>mine</h1>")
        (old / "pictures" / "a.png").write_bytes(b"x" * 1234)
        d = preview.ensure_site("oldie")
        self.assertEqual((d / "index.html").read_text(), "<h1>mine</h1>")
        self.assertEqual((d / "pictures" / "a.png").stat().st_size, 1234)
        self.assertTrue((old / "index.html").is_file())            # backup untouched, nothing deleted
        w = preview.where("oldie")
        self.assertEqual(w["folder"], str(d))
        self.assertEqual(w["backup"], str(old))
        self.assertEqual(w["files"], 2)

    def test_default_files_home_is_hermes_data(self):
        os.environ.pop("AILAB_HOME", None)
        self.assertEqual(config.files_home(), Path.home() / "hermes-data" / "ailab")
        os.environ["AILAB_HOME"] = self.tmp.name

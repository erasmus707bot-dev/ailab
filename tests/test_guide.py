"""🧭 errors guide the next step + no undefined names in the Lab's code (2026-11-25: video.py used `looks` unimported)."""
import ast
import builtins
import errno
import unittest
from pathlib import Path

from ailab import guide

PKG = Path(guide.__file__).resolve().parent


def undefined_names(src: str) -> list[tuple[str, int]]:
    """Names read somewhere in the file that are never bound anywhere in it (import, def, assign, arg, loop, with,
    except, comprehension, global) and aren't builtins. Coarse on purpose: no false alarms, catches a missing import."""
    tree = ast.parse(src)
    bound = set(dir(builtins)) | {"__file__", "__name__", "__doc__", "__package__", "__spec__", "__class__"}
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            bound.add(n.name)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            a = n.args
            for x in a.posonlyargs + a.args + a.kwonlyargs + [a.vararg, a.kwarg]:
                if x:
                    bound.add(x.arg)
        elif isinstance(n, (ast.Import, ast.ImportFrom)):
            for al in n.names:
                bound.add((al.asname or al.name).split(".")[0])
        elif isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del)):
            bound.add(n.id)
        elif isinstance(n, ast.ExceptHandler) and n.name:
            bound.add(n.name)
        elif isinstance(n, (ast.Global, ast.Nonlocal)):
            bound.update(n.names)
        elif hasattr(ast, "MatchAs") and isinstance(n, (ast.MatchAs, ast.MatchStar)) and n.name:
            bound.add(n.name)
    return sorted({(n.id, n.lineno) for n in ast.walk(tree)
                   if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load) and n.id not in bound})


class NoUndefinedNames(unittest.TestCase):
    def test_checker_catches_a_missing_import(self):
        self.assertEqual(undefined_names("def f():\n    return looks.x\n"), [("looks", 2)])
        self.assertEqual(undefined_names("from . import looks\ndef f(a, *b, **c):\n    return [looks.x for q in a if q] + list(b)\n"), [])

    def test_every_lab_file(self):
        bad = {}
        for f in sorted(PKG.rglob("*.py")):
            miss = undefined_names(f.read_text())
            if miss:
                bad[str(f.relative_to(PKG))] = miss
        self.assertEqual(bad, {}, "a name is used but never imported or defined")


class Explain(unittest.TestCase):
    def boom(self, exc):
        try:
            raise exc
        except Exception as e:                                         # noqa: BLE001
            return guide.explain(e, where="test")

    def test_lab_bug_says_not_your_words_and_what_to_paste(self):
        try:
            guide.nope_not_here                                        # AttributeError raised from this test file
        except AttributeError as e:
            m = guide.explain(e)
        self.assertIn("🐞", m)
        self.assertIn("not your words", m)
        self.assertIn("👉", m)
        self.assertIn("Change ailab", m)
        self.assertIn("Fix AttributeError", m)
        self.assertIn("errors.log", m)
        self.assertNotIn("Traceback", m)

    def test_bug_names_the_file_and_line_inside_the_lab(self):
        try:
            guide.spot(None)                                           # breaks inside ailab/guide.py
        except AttributeError as e:
            m = guide.explain(e)
        self.assertRegex(m, r"ailab/guide\.py line \d+")

    def test_each_kind_gets_its_own_next_step(self):
        self.assertIn("🔌", self.boom(ConnectionError("urlopen error [Errno 111] Connection refused 127.0.0.1")))
        self.assertIn("Hermes", self.boom(ConnectionError("Connection refused")))
        self.assertIn("internet", self.boom(TimeoutError("The read operation timed out")))
        self.assertIn("📁", self.boom(FileNotFoundError("pictures/a.png")))
        self.assertIn("chown", self.boom(PermissionError("videos/")))
        self.assertIn("💾", self.boom(OSError(errno.ENOSPC, "No space left on device")))
        self.assertIn("🧠", self.boom(RuntimeError("CUDA out of memory")))
        m = self.boom(RuntimeError("weird"))
        self.assertIn("⚠️", m)
        self.assertIn("👉", m)

    def test_trace_goes_to_the_log_not_the_screen(self):
        self.boom(ValueError("xyzzy-marker"))
        self.assertIn("xyzzy-marker", guide.log_file().read_text())
        self.assertIn("Traceback", guide.log_file().read_text())

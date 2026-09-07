"""Unit tests for the pick-and-open extraction logic (no socket, no TTY)."""

import importlib.machinery
import importlib.util
import os
import tempfile
import unittest
from pathlib import Path

script = Path(__file__).resolve().parent.parent / "scripts" / "pick-and-open"
loader = importlib.machinery.SourceFileLoader("pick_and_open", str(script))
spec = importlib.util.spec_from_loader(loader.name, loader)
pick_and_open = importlib.util.module_from_spec(spec)
loader.exec_module(pick_and_open)


class StripTrailingPunctTests(unittest.TestCase):
    def test_strips_common_trailing_punctuation(self):
        self.assertEqual(
            pick_and_open.strip_trailing_punct("/tmp/foo.rs,"), "/tmp/foo.rs"
        )
        self.assertEqual(
            pick_and_open.strip_trailing_punct("/tmp/foo.rs)"), "/tmp/foo.rs"
        )

    def test_keeps_interior_punct(self):
        self.assertEqual(
            pick_and_open.strip_trailing_punct("/tmp/my.file.rs"), "/tmp/my.file.rs"
        )


class SplitLineColTests(unittest.TestCase):
    def test_plain_path(self):
        self.assertEqual(pick_and_open.split_line_col("/a/b.rs"), ("/a/b.rs", None, None))

    def test_line(self):
        self.assertEqual(pick_and_open.split_line_col("/a/b.rs:42"), ("/a/b.rs", 42, None))

    def test_line_col(self):
        self.assertEqual(
            pick_and_open.split_line_col("/a/b.rs:42:7"), ("/a/b.rs", 42, 7)
        )

    def test_colon_without_digits_is_kept(self):
        self.assertEqual(
            pick_and_open.split_line_col("/a/b:c"), ("/a/b:c", None, None)
        )


class ExtractTargetsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cwd = self.tmp.name
        Path(self.cwd, "src").mkdir()
        Path(self.cwd, "src", "app.py").write_text("print('hi')\n")
        Path(self.cwd, "README.md").write_text("readme\n")
        self.cwds = [self.cwd]

    def tearDown(self):
        self.tmp.cleanup()

    def test_absolute_existing_path(self):
        target = os.path.join(self.cwd, "src", "app.py")
        self.assertEqual(
            pick_and_open.extract_targets(f"see {target} for details", self.cwds),
            [target],
        )

    def test_absolute_path_with_line_suffix(self):
        target = os.path.join(self.cwd, "src", "app.py")
        self.assertEqual(
            pick_and_open.extract_targets(f"bug at {target}:12:3 here", self.cwds),
            [f"{target}:12:3"],
        )

    def test_relative_path_resolves_against_cwd(self):
        self.assertEqual(
            pick_and_open.extract_targets("open src/app.py now", self.cwds),
            [os.path.join(self.cwd, "src", "app.py")],
        )

    def test_tilde_path(self):
        home = Path.home()
        readme = home / "dotfiles" / "README.md"
        if not readme.is_file():
            self.skipTest("needs ~/dotfiles/README.md")
        self.assertEqual(
            pick_and_open.extract_targets("see ~/dotfiles/README.md", self.cwds),
            [str(readme)],
        )

    def test_file_url(self):
        target = os.path.join(self.cwd, "src", "app.py")
        self.assertEqual(
            pick_and_open.extract_targets(f"link file://{target}", self.cwds), [target]
        )

    def test_file_url_percent_encoded_and_fragment(self):
        target = os.path.join(self.cwd, "src", "app.py")
        quoted = urllib_quote(target)
        self.assertEqual(
            pick_and_open.extract_targets(f"open file://{quoted}#L12", self.cwds),
            [target],
        )

    def test_missing_file_dropped(self):
        self.assertEqual(
            pick_and_open.extract_targets("/no/such/file/exists.rs here", self.cwds), []
        )

    def test_url_authority_not_matched(self):
        self.assertEqual(
            pick_and_open.extract_targets("browse https://example.com/src/app.py", self.cwds),
            [],
        )

    def test_most_recent_first_and_dedup(self):
        target = os.path.join(self.cwd, "src", "app.py")
        other = os.path.join(self.cwd, "README.md")
        text = f"first {target} then {other} again {target}"
        self.assertEqual(
            pick_and_open.extract_targets(text, self.cwds), [target, other]
        )

    def test_trailing_punctuation_stripped(self):
        target = os.path.join(self.cwd, "src", "app.py")
        self.assertEqual(
            pick_and_open.extract_targets(f"edit {target}.", self.cwds), [target]
        )


def urllib_quote(value: str) -> str:
    return value.replace("/", "%2F").replace(".", "%2E")


if __name__ == "__main__":
    unittest.main()

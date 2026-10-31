from pathlib import Path
import shutil
import tempfile
import unittest

from scripts.check_share_ready import check, git
from scripts.generate_demo_data import demo_files


@unittest.skipUnless(shutil.which("git"), "Git is required for history checks")
class ShareCheckTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        git(self.root, "init", "--quiet")
        for relative, content in demo_files().items():
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        git(self.root, "add", "examples")
        self.commit()

    def commit(self):
        git(self.root, "-c", "user.name=Synthetic Test", "-c", "user.email=test@example.invalid", "-c", "commit.gpgsign=false", "commit", "--quiet", "-m", "Synthetic fixture")

    def test_synthetic_only_history_is_shareable(self):
        self.assertEqual(check(self.root)[0], [])

    def test_deleted_private_data_is_still_detected_in_history(self):
        private = self.root / "private.csv"
        private.write_text("synthetic private sentinel")
        git(self.root, "add", "private.csv")
        self.commit()
        git(self.root, "rm", "private.csv")
        self.commit()
        self.assertEqual(check(self.root, working_tree_only=True)[0], [])
        self.assertTrue(any("Git-historikken: private.csv" in error for error in check(self.root)[0]))

    def test_staged_real_data_cannot_hide_behind_restored_working_demo(self):
        relative, original = next(iter(demo_files().items()))
        path = self.root / relative
        path.write_bytes(b"synthetic changed sentinel")
        git(self.root, "add", relative)
        path.write_bytes(original)
        self.assertTrue(any("Staged demo" in error for error in check(self.root, working_tree_only=True)[0]))

    def test_forced_staged_private_output_is_detected(self):
        (self.root / ".gitignore").write_text("outputs/\n")
        output = self.root / "outputs" / "private.xlsx"
        output.parent.mkdir()
        output.write_bytes(b"synthetic output sentinel")
        self.assertEqual(check(self.root, working_tree_only=True)[0], [])
        git(self.root, "add", "-f", "outputs/private.xlsx")
        self.assertTrue(any("outputs/private.xlsx" in error for error in check(self.root, working_tree_only=True)[0]))


if __name__ == "__main__":
    unittest.main()

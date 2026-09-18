import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import verify  # noqa: E402


class VerifyHelpersTest(unittest.TestCase):
    def test_numstat_excludes_generated_and_binary(self):
        text = "10\t2\tsrc/verifi/a.py\n500\t0\tuv.lock\n-\t-\tlogo.png\n3\t1\tschemas/spec.json\n"
        diff = verify.parse_numstat(text)
        self.assertEqual(diff["changed_lines"], 12)
        self.assertEqual(len(diff["files"]), 4)

    def test_numstat_dedupes_committed_and_working_tree(self):
        diff = verify.parse_numstat("1\t1\ta.py\n1\t1\ta.py\n")
        self.assertEqual((diff["files"], diff["changed_lines"]), (["a.py"], 2))

    def test_protected_paths(self):
        paths = ["src/verifi/x.py", "AGENTS.md", ".opencode/skills/a/SKILL.md", "docs/architecture/overview.md", "docs/guides/x.md"]
        self.assertEqual(verify.protected_violations(paths), paths[1:4])

    def test_diff_verdict(self):
        self.assertEqual(verify.diff_verdict(10), "ok")
        self.assertEqual(verify.diff_verdict(verify.DIFF_WARN_LINES + 1), "warn")
        self.assertEqual(verify.diff_verdict(verify.DIFF_FAIL_LINES + 1), "fail")

    def test_red_run_requires_real_failure(self):
        self.assertTrue(verify.red_run_ok(1))
        self.assertTrue(verify.red_run_ok(2))
        self.assertFalse(verify.red_run_ok(0))
        self.assertFalse(verify.red_run_ok(5))


if __name__ == "__main__":
    unittest.main()

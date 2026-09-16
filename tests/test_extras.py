import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))

from audit_history import audit  # noqa: E402
from check_message import check, fix_message  # noqa: E402
from helpers import make_repo  # noqa: E402
from style_profile import profile_subjects  # noqa: E402

LOWER = ["fix typo in readme", "bump deps", "add retry to fetch", "remove dead code", "handle empty input",
         "fix flaky test", "update ci image", "drop python 3.8", "rename config key", "speed up parser"] * 2
LOWER_P = profile_subjects(LOWER)
SENT_P = profile_subjects(["Add pagination to the API.", "Fix token expiry.", "Bump dependencies.", "Update the README."] * 5)
CONV_P = profile_subjects(["feat(api): add pagination", "fix(auth): expire tokens", "chore: bump deps"] * 7)


class FixTests(unittest.TestCase):
    def test_strips_attribution_and_mechanical_style(self):
        msg = "feat: Add Feature.\n\nWhy line.\n\n🤖 Generated with Claude Code\nCo-Authored-By: Claude <noreply@anthropic.com>"
        fixed = fix_message(msg, LOWER_P)
        self.assertEqual(fixed, "add Feature\n\nWhy line.")
        self.assertTrue(check(fixed, LOWER_P).ok)

    def test_adds_period_and_capital_for_sentence_repo(self):
        self.assertEqual(fix_message("fix token expiry", SENT_P), "Fix token expiry.")

    def test_keeps_prefix_in_conventional_repo(self):
        self.assertEqual(fix_message("feat(api): Add pagination.", CONV_P), "feat(api): add pagination")

    def test_keeps_human_coauthor(self):
        msg = "fix typo\n\nCo-authored-by: Jane Doe <jane@example.com>"
        self.assertEqual(fix_message(msg, LOWER_P), msg)

    def test_cannot_fix_narration(self):
        fixed = fix_message("fix typo\n\nThis commit fixes a typo.", LOWER_P)
        self.assertFalse(check(fixed, LOWER_P).ok)

    def test_all_attribution_message_becomes_empty(self):
        self.assertEqual(fix_message("Co-Authored-By: Claude <x@y>", LOWER_P), "")


class AutofixHookTests(unittest.TestCase):
    def test_rewrites_command_when_mechanical(self):
        repo = make_repo(LOWER)
        cmd = 'git commit -m "$(cat <<\'EOF\'\nFix retry loop.\n\nCo-Authored-By: Claude <noreply@anthropic.com>\nEOF\n)"'
        proc = subprocess.run([sys.executable, str(ROOT / "hooks" / "pretooluse.py")],
                              input=json.dumps({"tool_name": "Bash", "cwd": str(repo), "tool_input": {"command": cmd}}),
                              capture_output=True, text=True, env={**os.environ, "WHEN_IN_ROME_AUTOFIX": "1"})
        data = json.loads(proc.stdout)
        out = data["hookSpecificOutput"]
        self.assertNotIn("permissionDecision", out)
        self.assertIn("fix retry loop", out["updatedInput"]["command"])
        self.assertNotIn("Co-Authored-By", out["updatedInput"]["command"])

    def test_still_denies_when_not_mechanical(self):
        repo = make_repo(LOWER)
        cmd = 'git commit -m "fix retry loop\n\nThis commit fixes the retry loop."'
        proc = subprocess.run([sys.executable, str(ROOT / "hooks" / "pretooluse.py")],
                              input=json.dumps({"tool_name": "Bash", "cwd": str(repo), "tool_input": {"command": cmd}}),
                              capture_output=True, text=True, env={**os.environ, "WHEN_IN_ROME_AUTOFIX": "1"})
        self.assertEqual(json.loads(proc.stdout)["hookSpecificOutput"]["permissionDecision"], "deny")


class AuditTests(unittest.TestCase):
    def test_counts_tells_against_human_baseline(self):
        repo = make_repo(LOWER)
        for i, msg in enumerate(["Add Comprehensive Feature\n\nCo-Authored-By: Claude <noreply@anthropic.com>",
                                 "fix crash\n\nThis commit fixes the crash.", "feat: add thing"]):
            (repo / f"x{i}.txt").write_text("1")
            subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
            subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", msg], check=True)
        a = audit(str(repo))
        self.assertEqual(a["commits"], 23)
        self.assertTrue(a["human_baseline"])
        self.assertEqual(a["tells"]["attribution"], 1)
        self.assertEqual(a["tells"]["narration"], 1)
        self.assertGreaterEqual(a["tells"]["style outlier"], 2)
        self.assertEqual(a["flagged"], 3)
        self.assertEqual(a["native_score"], round(100 * (1 - 3 / 23)))

    def test_no_baseline_counts_hard_tells_only(self):
        repo = make_repo(["Add Feature\n\nCo-Authored-By: Claude <a@b>"] * 4)
        a = audit(str(repo))
        self.assertFalse(a["human_baseline"])
        self.assertEqual(a["flagged"], 4)
        self.assertNotIn("style outlier", a["tells"])


class RangeTests(unittest.TestCase):
    def test_range_check_and_hard_only(self):
        repo = make_repo(LOWER)
        subprocess.run(["git", "-C", str(repo), "branch", "base"], check=True)
        (repo / "a.txt").write_text("1")
        subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
        subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "Add thing"], check=True)  # style only
        (repo / "b.txt").write_text("1")
        subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
        subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "add other\n\nCo-Authored-By: Claude <a@b>"], check=True)
        script = str(ROOT / "scripts" / "check_range.py")
        full = subprocess.run([sys.executable, script, "--repo", str(repo), "--base", "base", "--head", "HEAD", "--github"], capture_output=True, text=True)
        self.assertEqual(full.returncode, 1)
        self.assertIn("::error::", full.stdout)
        self.assertIn("2 of 2", full.stdout)
        hard = subprocess.run([sys.executable, script, "--repo", str(repo), "--base", "base", "--head", "HEAD", "--hard-only"], capture_output=True, text=True)
        self.assertEqual(hard.returncode, 1)
        self.assertIn("1 of 2", hard.stdout)
        body = repo / "body.md"
        body.write_text("## Summary\nx\n\n## Test plan\n- [ ] a\n- [ ] b\n- [ ] c")
        pr = subprocess.run([sys.executable, script, "--repo", str(repo), "--base", "HEAD", "--head", "HEAD",
                             "--pr-title", "add other", "--pr-body-file", str(body), "--hard-only"], capture_output=True, text=True)
        self.assertEqual(pr.returncode, 1)
        self.assertIn("Test plan", pr.stdout)

    def test_action_yml_parses_and_points_at_script(self):
        text = (ROOT / "action.yml").read_text(encoding="utf-8")
        self.assertIn("scripts/check_range.py", text)
        self.assertIn("using: composite", text)
        self.assertTrue((ROOT / ".pre-commit-hooks.yaml").exists())


if __name__ == "__main__":
    unittest.main()

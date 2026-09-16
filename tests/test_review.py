"""Regression tests for findings from the pre-release review."""
import json
import subprocess
import sys
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "hooks"))
sys.path.insert(0, str(ROOT / "tests"))

from check_message import check, fix_message  # noqa: E402
from helpers import make_repo  # noqa: E402
from pretooluse import extract_messages  # noqa: E402
from style_profile import first_word_case, has_ai_attribution, profile_subjects  # noqa: E402

LOWER = profile_subjects(["fix typo in readme", "bump deps", "add retry to fetch", "remove dead code", "handle empty input",
                          "fix flaky test", "update ci image", "drop python 3.8", "rename config key", "speed up parser"] * 4)
UPPER = profile_subjects(["Add pagination", "Fix token expiry", "Bump dependencies", "Update the README", "Handle a null user"] * 8)


class AttributionTests(unittest.TestCase):
    def test_humans_named_like_tools_pass(self):
        for m in ["fix typo\n\nCo-authored-by: Devin Smith <devin@example.com>",
                  "fix typo\n\nCo-authored-by: Claude Dupont <claude.dupont@example.org>",
                  "fix typo\n\nCo-authored-by: Bob Lee <bob@openai.com>"]:
            self.assertTrue(check(m, LOWER).ok, m)

    def test_tool_trailers_fail(self):
        for m in ["fix typo\n\nCo-authored-by: Claude <noreply@anthropic.com>",
                  "fix typo\n\nCo-authored-by: Claude Code <noreply@anthropic.com>",
                  "fix typo\n\nSigned-off-by: Claude <noreply@anthropic.com>",
                  "fix typo\n\nReviewed-by: Copilot",
                  "fix typo\n\nHelped-by: Claude",
                  "fix typo\n\nCo-authored-by: Cursor Agent <cursoragent@cursor.com>",
                  "fix typo\n\nCo-authored-by: Cline <cline@example.com>",
                  "fix typo\n\nCo-authored-by: Kimi <k@k>",
                  "fix typo\n\nGenerated with AI",
                  "fix typo\n\nAI-generated commit",
                  "fix typo\n\nWritten with the help of ChatGPT"]:
            self.assertFalse(check(m, LOWER).ok, m)

    def test_only_tool_hosts_count(self):
        self.assertIsNone(has_ai_attribution("Co-authored-by: Bob Lee <bob@openai.com>"))
        self.assertIsNotNone(has_ai_attribution("Co-authored-by: Codex <noreply@openai.com>"))
        self.assertIsNotNone(has_ai_attribution("Co-authored-by: dependabot[bot] <x@y>"))


class CaseTests(unittest.TestCase):
    def test_identifiers_are_not_case_judged(self):
        for subj in ["3D model export", "iOS crash on rotate", "npm audit fix", "2x faster startup", "v1.2.3",
                     "UTF-8 support in parser", "SHA-256 checksums", "GitHub Actions cache"]:
            self.assertTrue(check(subj, LOWER).ok, (subj, check(subj, LOWER).failures))
            self.assertTrue(check(subj, UPPER).ok, (subj, check(subj, UPPER).failures))
        self.assertTrue(check("use std::mem::take in parser", LOWER).ok)
        # "use" is an ordinary verb: in a sentence-case repo a person would capitalise it.
        self.assertFalse(check("use std::mem::take in parser", UPPER).ok)
        self.assertIsNone(first_word_case("iOS crash"))
        self.assertIsNone(first_word_case("GitHub Actions cache"))
        self.assertEqual(first_word_case("Fix it"), "upper")
        self.assertEqual(first_word_case("fix it"), "lower")

    def test_fix_message_leaves_identifiers_alone(self):
        self.assertEqual(fix_message("iOS crash on rotate", UPPER), "iOS crash on rotate")
        self.assertEqual(fix_message("GitHub Actions cache", LOWER), "GitHub Actions cache")

    def test_emoji_regex_boundaries(self):
        self.assertTrue(check("use std::mem::take in parser", LOWER).ok)
        self.assertTrue(check("✓ mark passing tests", LOWER).ok)
        self.assertFalse(check("✨ add dark mode", LOWER).ok)
        self.assertFalse(check(":sparkles: add dark mode", LOWER).ok)


class PhrasingTests(unittest.TestCase):
    def test_product_wording_about_the_user_passes(self):
        for m in ["show hint when the user wants to undo", "log when the user requested a reset"]:
            self.assertTrue(check(m, LOWER).ok, m)

    def test_reapply_is_exempt(self):
        self.assertTrue(check('Reapply "add retry to client"', LOWER).ok)

    def test_regex_is_linear_on_whitespace_bombs(self):
        bomb = "x\n\nCo-authored-by: Claude <noreply@anthropic.com>\n" + "\n" * 200000 + "y"
        t = time.time()
        r = check(bomb, LOWER)
        self.assertLess(time.time() - t, 1.0)
        self.assertFalse(r.ok)
        # Attribution buried past the scan window is not seen, but the check stays fast.
        t = time.time()
        check("x\n" + "\n" * 200000 + "y\n\nCo-authored-by: Claude <noreply@anthropic.com>", LOWER)
        self.assertLess(time.time() - t, 1.0)


class ExtractTests(unittest.TestCase):
    def test_env_and_global_options(self):
        for cmd in ['git -C /p commit -m "fix it"', 'git -c a=b commit -m "fix it"', 'GIT_EDITOR=true git commit -m "fix it"',
                    'env X=1 git commit -m "fix it"', 'git commit -m"fix it"', 'git --no-pager commit -am "fix it"']:
            self.assertEqual(extract_messages(cmd), [("commit", "fix it")], cmd)

    def test_stdin_forms(self):
        self.assertEqual(extract_messages("git commit -F - <<'EOF'\nfix it\nEOF"), [("commit", "fix it")])
        self.assertEqual(extract_messages("printf 'x' | git commit -F -"), [("unreadable", "")])
        self.assertEqual(extract_messages("git commit -F /dev/stdin"), [("unreadable", "")])

    def test_relative_file_resolves_against_cwd(self):
        repo = make_repo(["fix a", "fix b", "fix c", "fix d", "fix e"])
        (repo / "sub").mkdir()
        (repo / "sub" / "msg.txt").write_text("fix it\n\nCo-authored-by: Claude <noreply@anthropic.com>\n")
        out = extract_messages("git commit -F msg.txt", cwd=str(repo / "sub"))
        self.assertEqual(out[0][0], "commit")
        self.assertIn("Co-authored-by", out[0][1])

    def test_unreadable_is_denied_by_hook(self):
        repo = make_repo(["fix a", "fix b", "fix c", "fix d", "fix e"])
        proc = subprocess.run([sys.executable, str(ROOT / "hooks" / "pretooluse.py")],
                              input=json.dumps({"tool_name": "Bash", "cwd": str(repo), "tool_input": {"command": "printf 'x' | git commit -F -"}}),
                              capture_output=True, text=True)
        self.assertEqual(json.loads(proc.stdout)["hookSpecificOutput"]["permissionDecision"], "deny")


class CliTests(unittest.TestCase):
    def test_hash_lines_kept_for_m_and_pr(self):
        script = str(ROOT / "scripts" / "check_message.py")
        body = "## Summary\n- x\n\n## Test plan\n- [ ] a\n- [ ] b\n- [ ] c"
        pr = subprocess.run([sys.executable, script, "--pr", "--title", "add x", "--body", body, "--profile", "/dev/null"] if False else
                            [sys.executable, script, "--pr", "--title", "add x", "--body", body, "--repo", str(make_repo(["fix a"] * 6))],
                            capture_output=True, text=True)
        self.assertEqual(pr.returncode, 1)
        self.assertIn("Test plan", pr.stdout)
        m = subprocess.run([sys.executable, script, "-m", "fix it\n\n#123 was the cause", "--repo", str(make_repo(["fix a"] * 6))],
                           capture_output=True, text=True)
        self.assertEqual(m.returncode, 0, m.stdout)


if __name__ == "__main__":
    unittest.main()

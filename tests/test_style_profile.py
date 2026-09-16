import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))

from helpers import make_repo  # noqa: E402
from style_profile import profile_repo, profile_subjects, rules_for, subject_limit  # noqa: E402

LOWER = ["fix typo in readme", "bump deps", "add retry to fetch", "remove dead code", "handle empty input",
         "fix flaky test", "update ci image", "drop python 3.8", "rename config key", "speed up parser"] * 4
CONV = ["feat(api): add pagination", "fix(auth): expire tokens", "chore: bump deps", "docs: update readme",
        "refactor(db): split queries", "test: cover empty input", "ci: cache node_modules", "fix: handle null user",
        "feat: add dark mode", "perf(parser): avoid copies"] * 4
SENTENCE = ["Add pagination to the API.", "Fix token expiry.", "Bump dependencies.", "Update the README.",
            "Split database queries.", "Cover the empty-input case.", "Cache node_modules in CI.", "Handle a null user.",
            "Add dark mode.", "Avoid copies in the parser."] * 4


class ProfileTests(unittest.TestCase):
    def test_lowercase_terse(self):
        p = profile_subjects(LOWER)
        s = p["subject"]
        self.assertGreaterEqual(s["lower_ratio"], 0.9)
        self.assertLessEqual(s["conventional_ratio"], 0.1)
        self.assertLessEqual(s["trailing_period_ratio"], 0.1)
        self.assertGreaterEqual(s["imperative_ratio"], 0.7)
        self.assertEqual(p["confidence"], "high")
        r = " ".join(rules_for(p))
        self.assertIn("lowercase", r)
        self.assertIn("does not use Conventional Commits", r)
        self.assertIn("No trailing period", r)

    def test_conventional(self):
        p = profile_subjects(CONV)
        self.assertGreaterEqual(p["subject"]["conventional_ratio"], 0.9)
        self.assertGreaterEqual(p["subject"]["lower_ratio"], 0.9, "case is judged after the prefix")
        self.assertIn("Conventional Commits prefixes are used", " ".join(rules_for(p)))

    def test_sentence_with_period(self):
        p = profile_subjects(SENTENCE)
        self.assertGreaterEqual(p["subject"]["upper_ratio"], 0.9)
        self.assertGreaterEqual(p["subject"]["trailing_period_ratio"], 0.9)
        self.assertIn("end with a period", " ".join(rules_for(p)))

    def test_bodies_and_bullets(self):
        bodies = ["because the old one broke on py3.8"] * 30 + [""] * 10
        p = profile_subjects(LOWER, bodies)
        self.assertGreaterEqual(p["body"]["ratio"], 0.7)
        self.assertIn("Most commits have a body", " ".join(rules_for(p)))
        p2 = profile_subjects(LOWER, [""] * 40)
        self.assertIn("Bodies are rare", " ".join(rules_for(p2)))

    def test_empty_and_limits(self):
        self.assertEqual(profile_subjects([])["count"], 0)
        self.assertEqual(subject_limit({"count": 0}), 50)
        self.assertEqual(subject_limit(profile_subjects(["x" * 90] * 10)), 72)
        self.assertEqual(subject_limit(profile_subjects(["fix"] * 10)), 50)

    def test_samples_are_from_history(self):
        p = profile_subjects(LOWER)
        for s in p["samples"]:
            self.assertIn(s, LOWER)

    def test_repo_profile_excludes_bots_and_ai_trailers(self):
        d = make_repo(LOWER[:10])
        import subprocess
        env_bot = {"GIT_AUTHOR_NAME": "dependabot[bot]", "GIT_AUTHOR_EMAIL": "b@b", "GIT_COMMITTER_NAME": "x", "GIT_COMMITTER_EMAIL": "x@x"}
        (d / "bot.txt").write_text("1")
        subprocess.run(["git", "-C", str(d), "add", "-A"], check=True)
        subprocess.run(["git", "-C", str(d), "commit", "-q", "-m", "Bump lodash from 1 to 2"], check=True, env={**__import__("os").environ, **env_bot})
        (d / "ai.txt").write_text("1")
        subprocess.run(["git", "-C", str(d), "add", "-A"], check=True)
        subprocess.run(["git", "-C", str(d), "commit", "-q", "-m", "Add Comprehensive Feature\n\nCo-Authored-By: Claude <noreply@anthropic.com>"], check=True)
        p = profile_repo(str(d))
        self.assertEqual(p["count"], 10)
        self.assertEqual(p["excluded_bot_or_ai_commits"], 2)

    def test_branch_style(self):
        d = make_repo(LOWER[:6], branches=["feature/add-login", "feature/fix-cache", "bugfix/null-user", "chore/deps"])
        p = profile_repo(str(d))
        self.assertEqual(p["branches"]["count"], 4)
        self.assertGreaterEqual(p["branches"]["slash_prefix_ratio"], 0.9)
        self.assertEqual(p["branches"]["separator"], "kebab")
        self.assertIn("feature/", " ".join(rules_for(p)))


if __name__ == "__main__":
    unittest.main()

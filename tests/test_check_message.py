import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from check_message import check  # noqa: E402
from style_profile import profile_subjects  # noqa: E402

LOWER = profile_subjects(["fix typo in readme", "bump deps", "add retry to fetch", "remove dead code", "handle empty input",
                          "fix flaky test", "update ci image", "drop python 3.8", "rename config key", "speed up parser"] * 4)
CONV = profile_subjects(["feat(api): add pagination", "fix(auth): expire tokens", "chore: bump deps", "docs: update readme",
                         "refactor(db): split queries", "test: cover empty input", "ci: cache node_modules", "fix: handle null user",
                         "feat: add dark mode", "perf(parser): avoid copies"] * 4)
SENTENCE = profile_subjects(["Add pagination to the API.", "Fix token expiry.", "Bump dependencies.", "Update the README.",
                             "Split database queries.", "Cover the empty-input case.", "Cache node_modules in CI.", "Handle a null user.",
                             "Add dark mode.", "Avoid copies in the parser."] * 4)


class HardRuleTests(unittest.TestCase):
    def test_ai_trailer_fails_everywhere(self):
        for prof in (LOWER, CONV, SENTENCE, {"count": 0}):
            r = check("fix typo\n\nCo-Authored-By: Claude <noreply@anthropic.com>", prof)
            self.assertFalse(r.ok)
            self.assertTrue(any("attribution" in f for f in r.failures))

    def test_generated_with_line(self):
        r = check("fix typo\n\n🤖 Generated with Claude Code", LOWER)
        self.assertFalse(r.ok)

    def test_human_coauthor_is_fine(self):
        r = check("fix typo\n\nCo-authored-by: Jane Doe <jane@example.com>", LOWER)
        self.assertTrue(r.ok, r.failures)

    def test_narration_fails(self):
        r = check("fix typo\n\nThis commit fixes a typo in the readme.", LOWER)
        self.assertFalse(r.ok)
        self.assertTrue(any("Narration" in f for f in r.failures))

    def test_process_talk_fails(self):
        r = check("fix typo as requested", LOWER)
        self.assertFalse(r.ok)

    def test_marketing_word_is_a_warning(self):
        r = check("add robust retry", LOWER)
        self.assertTrue(r.ok)
        self.assertTrue(any("Marketing" in w for w in r.warnings))

    def test_empty(self):
        self.assertFalse(check("", LOWER).ok)


class StyleTests(unittest.TestCase):
    def test_native_lowercase_passes(self):
        self.assertTrue(check("fix windows ci", LOWER).ok)

    def test_capital_fails_in_lowercase_repo(self):
        r = check("Fix windows ci", LOWER)
        self.assertTrue(any("capital" in f for f in r.failures))

    def test_conventional_prefix_fails_in_plain_repo(self):
        r = check("fix: windows ci", LOWER)
        self.assertTrue(any("Conventional" in f for f in r.failures))

    def test_missing_prefix_fails_in_conventional_repo(self):
        r = check("add pagination", CONV)
        self.assertTrue(any("Missing the feat" in f for f in r.failures))
        self.assertTrue(check("feat(api): add pagination", CONV).ok)

    def test_period_rules(self):
        self.assertTrue(any("Trailing period" in f for f in check("fix typo.", LOWER).failures))
        self.assertTrue(any("No trailing period" in f for f in check("Fix typo", SENTENCE).failures))
        self.assertTrue(check("Fix the typo.", SENTENCE).ok)

    def test_lowercase_fails_in_sentence_repo(self):
        self.assertTrue(any("capitalises" in f for f in check("fix the typo.", SENTENCE).failures))

    def test_length(self):
        r = check("fix " + "x" * 80, LOWER)
        self.assertTrue(any("chars" in f for f in r.failures))

    def test_past_tense_fails_in_imperative_repo(self):
        r = check("fixed windows ci", LOWER)
        self.assertTrue(any("Past tense" in f for f in r.failures))

    def test_emoji(self):
        self.assertTrue(any("Emoji" in f for f in check("✨ add dark mode", LOWER).failures))

    def test_long_body_in_bodyless_repo_warns(self):
        r = check("fix ci\n\n- one\n- two\n- three\n- four", LOWER)
        self.assertTrue(r.ok)
        self.assertTrue(any("Body has" in w for w in r.warnings))

    def test_no_profile_only_hard_rules(self):
        self.assertTrue(check("Fix the typo", {"count": 0}).ok)
        self.assertTrue(check("fix: typo", {"count": 0}).ok)


class PRTests(unittest.TestCase):
    def test_stock_template_fails(self):
        body = "## Summary\n- did stuff\n\n## Test plan\n- [ ] ran tests\n- [ ] checked\n- [ ] more"
        r = check("add login\n\n" + body, LOWER, kind="pr")
        self.assertFalse(r.ok)
        self.assertTrue(any("Summary / ## Test plan" in f for f in r.failures))

    def test_plain_pr_passes(self):
        r = check("add login\n\nAdds the login form and wires it to the session API. Tested by logging in locally.", LOWER, kind="pr")
        self.assertTrue(r.ok, r.failures)


if __name__ == "__main__":
    unittest.main()

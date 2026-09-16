import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "hooks"))
sys.path.insert(0, str(ROOT / "tests"))

from helpers import make_repo  # noqa: E402
from pretooluse import extract_messages  # noqa: E402

LOWER = ["fix typo in readme", "bump deps", "add retry to fetch", "remove dead code", "handle empty input",
         "fix flaky test", "update ci image", "drop python 3.8", "rename config key", "speed up parser"] * 2


def run_hook(script, payload, cwd=None):
    proc = subprocess.run([sys.executable, str(ROOT / "hooks" / script)], input=json.dumps(payload),
                          capture_output=True, text=True, encoding="utf-8", timeout=60, cwd=cwd)
    return proc.returncode, proc.stdout


class ExtractTests(unittest.TestCase):
    def test_simple_m(self):
        self.assertEqual(extract_messages('git commit -m "fix typo"'), [("commit", "fix typo")])

    def test_am_and_chain(self):
        self.assertEqual(extract_messages("git add -A && git commit -am 'fix typo' && git push"), [("commit", "fix typo")])

    def test_multiple_m(self):
        self.assertEqual(extract_messages('git commit -m "subject" -m "body line"'), [("commit", "subject\n\nbody line")])

    def test_heredoc(self):
        cmd = 'git commit -m "$(cat <<\'EOF\'\nfix typo\n\nlonger body\nEOF\n)"'
        self.assertEqual(extract_messages(cmd), [("commit", "fix typo\n\nlonger body")])

    def test_amend_without_message_is_ignored(self):
        self.assertEqual(extract_messages("git commit --amend --no-edit"), [])

    def test_non_git(self):
        self.assertEqual(extract_messages("ls -la && echo commit"), [])

    def test_gh_pr_create(self):
        cmd = 'gh pr create --title "add login" --body "$(cat <<\'EOF\'\n## Summary\nstuff\n## Test plan\n- [ ] x\nEOF\n)"'
        out = extract_messages(cmd)
        self.assertEqual(out[0][0], "pr")
        self.assertTrue(out[0][1].startswith("add login\n\n## Summary"))

    def test_unbalanced_quotes_do_not_crash(self):
        self.assertEqual(extract_messages('git commit -m "oops'), [])


class HookProcessTests(unittest.TestCase):
    def setUp(self):
        self.repo = make_repo(LOWER)

    def test_denies_ai_style_commit(self):
        cmd = 'git commit -m "$(cat <<\'EOF\'\nfeat: Add Comprehensive Feature.\n\nCo-Authored-By: Claude <noreply@anthropic.com>\nEOF\n)"'
        code, out = run_hook("pretooluse.py", {"tool_name": "Bash", "cwd": str(self.repo), "tool_input": {"command": cmd}})
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertEqual(data["hookSpecificOutput"]["permissionDecision"], "deny")
        reason = data["hookSpecificOutput"]["permissionDecisionReason"]
        self.assertIn("attribution", reason)
        self.assertIn("House style", reason)
        self.assertIn("Real subjects", reason)

    def test_allows_native_commit(self):
        code, out = run_hook("pretooluse.py", {"tool_name": "Bash", "cwd": str(self.repo), "tool_input": {"command": 'git commit -m "fix retry loop"'}})
        self.assertEqual((code, out), (0, ""))

    def test_ignores_other_tools_and_commands(self):
        self.assertEqual(run_hook("pretooluse.py", {"tool_name": "Read", "tool_input": {"file_path": "x"}}), (0, ""))
        self.assertEqual(run_hook("pretooluse.py", {"tool_name": "Bash", "cwd": str(self.repo), "tool_input": {"command": "git status"}}), (0, ""))

    def test_ignores_commands_that_merely_mention_pr_or_commit(self):
        for cmd in ["npm run prod", "echo commit", "git log --oneline | grep commit", "gh pr list"]:
            self.assertEqual(run_hook("pretooluse.py", {"tool_name": "Bash", "cwd": str(self.repo), "tool_input": {"command": cmd}}), (0, ""), cmd)

    def test_garbage_input_is_allowed(self):
        proc = subprocess.run([sys.executable, str(ROOT / "hooks" / "pretooluse.py")], input="not json", capture_output=True, text=True)
        self.assertEqual((proc.returncode, proc.stdout), (0, ""))

    def test_off_switch(self):
        cmd = 'git commit -m "feat: Bad.\n\nCo-Authored-By: Claude <x@y>"'
        proc = subprocess.run([sys.executable, str(ROOT / "hooks" / "pretooluse.py")],
                              input=json.dumps({"tool_name": "Bash", "cwd": str(self.repo), "tool_input": {"command": cmd}}),
                              capture_output=True, text=True, env={**os.environ, "WHEN_IN_ROME_OFF": "1"})
        self.assertEqual((proc.returncode, proc.stdout), (0, ""))

    def test_sessionstart_injects_rules(self):
        code, out = run_hook("sessionstart.py", {"cwd": str(self.repo), "hook_event_name": "SessionStart"})
        self.assertEqual(code, 0)
        data = json.loads(out)
        ctx = data["hookSpecificOutput"]["additionalContext"]
        self.assertIn("lowercase", ctx)
        self.assertIn("Never add AI attribution", ctx)

    def test_sessionstart_silent_outside_repo(self):
        import tempfile
        code, out = run_hook("sessionstart.py", {"cwd": tempfile.mkdtemp()})
        self.assertEqual((code, out), (0, ""))


class GitHookInstallTests(unittest.TestCase):
    def test_install_and_reject(self):
        repo = make_repo(LOWER)
        subprocess.run([sys.executable, str(ROOT / "scripts" / "install_git_hook.py"), "--repo", str(repo)], check=True, capture_output=True)
        (repo / "new.txt").write_text("x")
        subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
        bad = subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "Feat: Added Stuff.\n\nCo-Authored-By: Claude <a@b>"], capture_output=True, text=True)
        self.assertNotEqual(bad.returncode, 0)
        self.assertIn("attribution", bad.stdout + bad.stderr)
        good = subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "add new file"], capture_output=True, text=True)
        self.assertEqual(good.returncode, 0, good.stderr)
        subprocess.run([sys.executable, str(ROOT / "scripts" / "install_git_hook.py"), "--repo", str(repo), "--uninstall"], check=True, capture_output=True)
        self.assertFalse((repo / ".git" / "hooks" / "commit-msg").exists())


if __name__ == "__main__":
    unittest.main()

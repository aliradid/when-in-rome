# Changelog

## [1.1.0] — 2026-09-16

- `audit_history.py`: scan any repo and get a native score, tell counts and the
  worst offenders. No human baseline means hard tells only.
- GitHub Action (`uses: aliradid/when-in-rome@v1`): fail pull requests whose commits
  or description carry AI tells; optional style enforcement.
- `check_range.py` for CI, `.pre-commit-hooks.yaml` for pre-commit users.
- `check_message.py --fix` and `WHEN_IN_ROME_AUTOFIX=1`: mechanical fixes
  (attribution lines, case, period, prefix) applied in place; narration and wording
  still bounce back to the author.
- Hooks fall back to `python` where `python3` is missing (Windows).

## [1.0.0] — 2026-09-16

First release.

- Skill: read the repo's history before any commit, branch or PR and match it.
- `style_profile.py`: house-style profile from human commits (bots and AI-attributed
  commits excluded), with plain-language rules and real sample subjects.
- `check_message.py`: hard tells (attribution, narration, stock PR template) and
  style tells judged against the profile.
- Claude Code hooks: PreToolUse blocks `git commit` / `gh pr create` that would not
  pass; SessionStart tells the agent the house style up front.
- `install_git_hook.py`: the same check as a git commit-msg hook.
- Installers for Claude Code, Codex, Cursor, Gemini CLI, OpenCode, Kimi, Qwen,
  Copilot, Zed, Grok.
- Deterministic and live evals.

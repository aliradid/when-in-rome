# Changelog

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

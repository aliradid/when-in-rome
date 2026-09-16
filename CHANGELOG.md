# Changelog

## [1.1.1] — 2026-09-16

Fixes from a pre-release review.

- GitHub Action: fetch the pull request commits and the base history explicitly, so it
  works on the default shallow checkout (before, it checked only the merge commit).
- Regexes made linear on whitespace-heavy bodies; messages are scanned up to 8 KB, so a
  crafted commit can no longer push the hook past its timeout.
- Hook parsing: env prefixes, `git -C`/`-c` global options, `-m"attached"`, `-F -` with
  a heredoc; stdin-only messages the hook cannot read are refused rather than allowed;
  `-F` paths resolve against the session's working directory.
- Attribution: tool names must be the whole name or a tool email host, so people named
  Devin or Claude pass; `Signed-off-by`/`Reviewed-by`/`Helped-by` tool trailers,
  "Generated with AI", "AI-generated" and more agent names are caught.
- Case checks skip identifiers (iOS, GitHub, npm, 3D, UTF-8); `fix_message` no longer
  rewrites them. Emoji detection no longer matches `std::mem::take` or a check mark.
- Merge, revert, reapply, fixup and squash messages are exempt from style checks.
- "the user wants ..." and "as discussed" are warnings, not failures.
- `#` lines are stripped only when reading a file, so PR bodies and `-m` keep them.
- Bot commits are skipped in CI ranges; history samples are quoted as data.
- pre-commit hook uses `language: script`; docs say to install the commit-msg stage.

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

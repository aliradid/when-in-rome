# Agent guide

| Area | Location |
| --- | --- |
| Canonical skill | `skills/when-in-rome/SKILL.md` |
| References | `skills/when-in-rome/references/` |
| Profiler | `scripts/style_profile.py` |
| Checker | `scripts/check_message.py` |
| Git hook installer | `scripts/install_git_hook.py` |
| Claude Code hooks | `hooks/hooks.json`, `hooks/pretooluse.py`, `hooks/sessionstart.py` |
| Cursor mirror | `.cursor/skills/when-in-rome/SKILL.md` (byte-identical, CI checks) |
| Other platforms | `.claude-plugin/`, `.codex-plugin/`, `.agents/`, `.opencode/`, `gemini-extension.json`, `GEMINI.md`, `kimi.plugin.json`, `qwen-extension.json`, `plugin.json` |
| Evals | `evals/`, `scripts/run_evals.py` |
| Tests | `tests/` |

Change the skill or scripts first, sync the mirror, keep versions aligned. Verify with:

```bash
python3 -m unittest discover -s tests -v
python3 scripts/run_evals.py run
claude plugin validate .
```

Commits in this repo follow its own history: lowercase, short, no prefix.

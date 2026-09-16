# Install

Every route loads the same `skills/when-in-rome/SKILL.md`. The Claude Code and OpenCode
routes also get the enforcement hook that blocks commits and PRs which would not pass
as native. On other platforms the skill guides the agent and you can install the git
commit-msg hook for enforcement.

## Claude Code

```bash
claude plugin marketplace add aliradid/when-in-rome
claude plugin install when-in-rome@when-in-rome
```

That's it. From the next session, every `git commit` and `gh pr create` the agent runs
is checked against the repo's history first, and the house style is shown to the agent
at session start. `/when-in-rome` invokes the skill explicitly. Set
`WHEN_IN_ROME_OFF=1` to disable the hooks for a shell.

## Git commit-msg hook (any tool, any agent)

Rejects any commit whose message would stand out, whoever wrote it.

```bash
git clone https://github.com/aliradid/when-in-rome ~/.when-in-rome
python3 ~/.when-in-rome/scripts/install_git_hook.py --repo /path/to/your/repo
```

Remove with `--uninstall`. An existing commit-msg hook is kept as
`commit-msg.pre-when-in-rome` and restored on uninstall.

## Codex

```bash
codex plugin marketplace add aliradid/when-in-rome --ref main
codex plugin add when-in-rome@when-in-rome
```

Then `$when-in-rome` in a prompt. Always-on: add to `~/.codex/AGENTS.md`:

```markdown
Before any git commit, branch, or PR, read the repo's git history and match its
house style (case, length, prefixes, mood, bodies). Never add AI attribution lines.
```

## Cursor (and harnesses reading `~/.cursor/skills` or `.agents/skills`)

```bash
npx skills add aliradid/when-in-rome -a cursor -y
```

## Gemini CLI

```bash
mkdir -p ~/.gemini/commands
curl -fsSL https://raw.githubusercontent.com/aliradid/when-in-rome/main/skills/when-in-rome/agents/gemini.toml \
  -o ~/.gemini/commands/when-in-rome.toml
```

Or as an always-on extension: `gemini extensions install https://github.com/aliradid/when-in-rome`.

## OpenCode

```bash
git clone https://github.com/aliradid/when-in-rome ~/.config/opencode/vendor/when-in-rome
```

Add to `opencode.json`:

```json
{ "plugin": ["~/.config/opencode/vendor/when-in-rome/.opencode/plugins/when-in-rome.mjs"] }
```

The plugin injects the house style each turn and refuses bash `git commit` /
`gh pr create` calls that fail the check. Needs `python3` on PATH.

## Kimi Code CLI

`/plugins` → **Custom** → paste `https://github.com/aliradid/when-in-rome` → **Trust and install**. Then `/skill:when-in-rome`.

## Qwen Code

```bash
qwen extensions install aliradid/when-in-rome
```

## Grok

```bash
grok plugin install aliradid/when-in-rome --trust
grok plugin enable when-in-rome
```

## GitHub Copilot (VS Code)

```bash
npx skills add aliradid/when-in-rome -a github-copilot
```

## Zed

Agent Panel → Skills → **Create skill from URL** → paste
`https://github.com/aliradid/when-in-rome/blob/main/skills/when-in-rome/SKILL.md`.

## Anything else

Paste the body of `skills/when-in-rome/SKILL.md` into the system prompt, and install
the git commit-msg hook for enforcement.

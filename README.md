# when-in-rome

**When in Rome, commit as the Romans do.**

An agent skill plus an enforcement hook that makes AI-written commits, branch names
and pull requests look like they belong in the repo. It reads the project's own git
history, works out the house style, and writes in it. Then it blocks any commit or PR
that would stand out, including every AI attribution line.

```bash
claude plugin marketplace add aliradid/when-in-rome
claude plugin install when-in-rome@when-in-rome
```

Other harnesses and the git-hook route: [INSTALL.md](INSTALL.md).

## The problem

Open any repo where an agent has been committing and you can spot its commits without
reading the diff:

```
feat: Add Comprehensive Retry Logic to HTTP Client

This commit implements robust retry logic with exponential backoff to
ensure seamless handling of transient network failures.

🤖 Generated with Claude Code
Co-Authored-By: Claude <noreply@anthropic.com>
```

sitting between `fix typo` and `bump deps`. Every commit-message tool on GitHub makes
this worse by enforcing a template. Humans don't write to a template. They write like
the people around them.

## What it does

**Reads the room.** `style_profile.py` looks at the last 300 human commits (bots and
AI-attributed commits excluded) and reports what the history is consistent about:

```
House style from 214 human commits (confidence: high):
- Subjects start lowercase (94% of history).
- Typical subject is 31 characters; stay under 52.
- No trailing period on the subject.
- No feat:/fix:/chore: prefixes; this repo does not use Conventional Commits.
- No emoji.
- Imperative mood ('add', 'fix', 'remove'), not 'added' or 'adding'.
- Common first words: fix, add, remove, use, bump.
- Bodies are rare (12%): usually subject only; add a body only when the why is not obvious.
- Branch names use a prefix: feature/, fix/.
Representative subjects:
  fix off by one in pager
  add --json flag
  drop python 3.8
```

**Writes in it.** The skill tells the agent to profile first, then write the subject in
the repo's voice, add a body only when the repo does, keep one logical change per
commit, name branches the way `git branch -a` does, and write PR bodies the way merged
PRs in the repo are written.

**Blocks what doesn't pass.** A Claude Code PreToolUse hook checks every `git commit`
and `gh pr create` before it runs. Fail, and the agent gets the reasons plus the house
style back, and has to rewrite:

```
when-in-rome blocked this because the message would not pass as one of this repo's own:
- [commit] AI attribution line: 'Co-Authored-By: Claude <noreply@anthropic'. Remove it.
- [commit] Subject starts with a capital; this repo writes lowercase subjects.
- [commit] Conventional Commits prefix (feat:/fix:/...) but this repo does not use them.
- [commit] (warning) Marketing word 'comprehensive'; say concretely what changed.
House style from the history:
- Subjects start lowercase (94% of history).
...
```

The same check installs as an ordinary git `commit-msg` hook, so it works with any
agent, any editor, and any human.

## What counts as a tell

Hard failures anywhere: AI attribution lines, narration ("This commit ...", "In this
PR ..."), conversation leaks ("as requested"), the stock `## Summary / ## Test plan`
skeleton.

Style failures only when the history is at least 80% consistent the other way: first
letter case, subject length past the repo's 90th percentile, type prefixes present or
missing, trailing period, past tense, emoji.

Warnings: marketing words (comprehensive, robust, seamless, leverage, enhance,
streamline), tool names, checkbox test plans, a long body in a repo that never writes
them.

Details in [tells.md](skills/when-in-rome/references/tells.md) and
[examples.md](skills/when-in-rome/references/examples.md).

## Not about hiding anything

This does not pretend a human wrote the code. It stops agents from defacing a history
with templated messages and trailers that carry no information, and makes them write
the message a maintainer would have written: what changed, why, in the repo's own
words. Whether you disclose AI use is your policy; put it in the PR description or the
CONTRIBUTING file, where it belongs, not in every commit subject.

## Dials

| | |
| --- | --- |
| `/when-in-rome` | invoke the skill explicitly |
| `stop when-in-rome` | off for the session |
| `WHEN_IN_ROME_OFF=1` | disables the hooks for a shell |
| `CONTRIBUTING.md` or `commit.template` states a format | that wins over observed history |
| the user names a format | the user wins |

## Evals

Deterministic: a corpus of messages with known verdicts against three synthetic
histories; the checker must agree on all of them. Live: a throwaway repo with real
history and a real staged change, committed by the agent with the plugin loaded; the
result is scored by the checker. See [evals/README.md](evals/README.md).

```bash
python3 scripts/run_evals.py run
python3 scripts/run_evals.py live --runner claude
```

## Layout

```
skills/when-in-rome/SKILL.md      the skill (source of truth)
skills/when-in-rome/references/   tells, before/after examples
scripts/style_profile.py          house-style profiler
scripts/check_message.py          message checker (commit and PR modes)
scripts/install_git_hook.py       git commit-msg hook installer
hooks/                            Claude Code PreToolUse + SessionStart hooks
evals/                            histories, message corpus, live runner
```

No dependencies beyond Python 3 and git.

## Contributing

The most useful issue is "it let this through" or "it blocked this native message".
Paste the message and ten subjects from the repo's history. See
[CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT.

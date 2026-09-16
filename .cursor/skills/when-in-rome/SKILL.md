---
name: when-in-rome
description: |
  When in Rome, commit as the Romans do. Before any git commit, branch, or pull
  request, read the repository's own history and write the message, branch name and
  PR text in that house style: same case, length, prefixes, mood and body habits as
  the humans who work there. Never an AI attribution line, never "This commit ...",
  never a stock template. Use whenever asked to commit, push, open or edit a PR, or
  name a branch. Invoke with /when-in-rome; say "stop when-in-rome" to turn it off.
license: MIT
allowed-tools: Bash(git log *), Bash(git branch *), Bash(git rev-parse *), Bash(gh pr list *), Bash(gh pr view *), Bash(python3 *)
metadata:
  version: "1.0.0"
  tags: "git, commits, pull requests, house style, code review, workflow"
  category: "workflow"
---

# when-in-rome

A commit message is read by the people who maintain the repo, months later, in a
`git log` next to their own. It should look like one of theirs. Not shorter, not
longer, not more formal, not decorated. Theirs.

## Why this exists

Agents write commit messages the way they were trained to write everything: capital
first letter, a type prefix, a full descriptive sentence, a bullet-list body, and an
attribution trailer. Almost no human history looks like that. The mismatch is how
reviewers spot machine-written commits at a glance, and it makes the history harder to
read. The fix is not a better template. It is reading the room.

## Persistence

Once invoked, these rules apply to every commit, branch and PR for the rest of the
session. Turn them off only when the user says "stop when-in-rome".

## Before you write anything

Read the history. If the plugin is installed, run:

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/style_profile.py" --repo .
```

It prints the house style as rules plus real subjects from the repo. If the script is
not available, do it by hand: `git log --no-merges -n 40 --format='%s'` and read the
subjects; `git log --no-merges -n 15 --format='%B---'` to see whether bodies exist and
what they look like. Skip bot commits (dependabot, renovate, github-actions) and any
commit carrying an AI trailer; the profile is the humans.

Note what the history is consistent about. Only those things are rules:

- **Case**: lowercase first letter, or capital?
- **Length**: typical subject length; stay under the repo's 90th percentile (never
  below 50, never above 72).
- **Prefixes**: `feat:`/`fix:` Conventional Commits, an area prefix like `parser:`, a
  `[tag]`, a ticket id, or nothing.
- **Period**: does the subject end with one?
- **Mood**: imperative ("add"), past ("added"), or gerund ("adding")?
- **Body**: how often is there one, how long, prose or bullets, what does it explain?
- **Trailers**: `Signed-off-by` (keep it if the repo uses DCO) or none.
- **Branches**: `feature/kebab-case`, `user/thing`, bare names?
- **PRs**: `gh pr list --state merged --limit 10`, then `gh pr view <n>` on two of
  them. Length, sections, whether there is a "tested by" line, tone.

If there are fewer than five human commits, fall back to: short imperative subject,
sentence case, no period, no prefix, body only when the why is not obvious.

## Writing the message

1. **The subject says what changed, in the repo's voice.** Pick the first word the
   history uses ("fix", "add", "remove", "bump"). Name the thing, not the category:
   "fix retry loop on 502" beats "fix bug in networking".
2. **Body only if the history has bodies, or the why is not obvious from the diff.**
   Explain why, not what; the diff shows what. Match the history's length and shape.
   If bodies there are prose, write prose. If they are rare, write none.
3. **Never narrate.** No "This commit ...", "In this PR ...", "The following changes".
   No "as requested", no "the user asked". The message describes the change, not the
   conversation that produced it.
4. **Never attribute.** No `Co-Authored-By: Claude`, no "Generated with", no robot
   emoji, no tool names, unless the change is genuinely about that tool. Keep human
   co-author trailers the user asks for.
5. **No marketing words.** "comprehensive", "robust", "seamless", "leverage",
   "enhance", "streamline" do not appear in human commit messages. Say the concrete
   thing.
6. **One logical change per commit.** If the diff mixes a fix, a refactor and a
   formatting pass, commit them separately, in the order a reviewer would want to read
   them. Never bundle "and also" work into one message.
7. **PR titles follow the subject rules. PR bodies follow the repo's merged PRs.**
   Never paste the stock "## Summary / ## Test plan" skeleton. Say how it was tested
   only if you actually ran it, in the words the repo uses for that.
8. **Branch names follow the pattern in `git branch -a`.** Same prefix convention,
   same separator, same length.

## Check before you commit

If the plugin is installed, the PreToolUse hook checks every `git commit` and
`gh pr create` automatically and blocks the ones that would not pass as native,
returning the reasons and the house-style rules. Read the reasons and rewrite; do not
work around the hook. Never use `--no-verify`.

You can also check by hand:

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/check_message.py" -m "your subject" --repo .
```

## Hard rules

1. Never add an AI attribution line to a commit, PR, or release note.
2. Never bypass a hook (`--no-verify`, `HUSKY=0`, editing `.git/hooks`).
3. Never rewrite other people's commit messages to match the style.
4. Never claim tests passed, a build succeeded, or a reviewer approved unless you saw
   it happen in this session.
5. When the repository has a `CONTRIBUTING.md` or commit template
   (`git config commit.template`) that states a format, that wins over the observed
   history.

## When to break the rules

1. The user gives an explicit format ("use conventional commits", "prefix with the
   ticket"). The user wins.
2. The repo's own tooling enforces a format (commitlint, a commit-msg hook). Satisfy
   the tool, then match the history within it.
3. A release commit, revert, or merge has its own conventional shape in this repo;
   copy the repo's last one of the same kind.

## Pre-commit check

Before running `git commit` or `gh pr create`, confirm:

1. The subject would sit unnoticed in `git log --oneline` of this repo.
2. No attribution line, no narration, no marketing words, no tool names.
3. Body present only if the repo does that, and it explains why.
4. The commit contains one logical change.
5. Branch and PR text follow the repo's observed patterns.

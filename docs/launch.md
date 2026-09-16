# Launch copy

Drafts for posting. Edit to taste; keep the numbers honest.

## Show HN

**Title:** Show HN: when-in-rome – make AI agents commit in your repo's own style, or block them

**Body:**

Every coding agent writes commit messages the same way: `feat:` prefix, capitalised
sentence, a bullet-list body, and a `Co-Authored-By: Claude` trailer. Drop that into a
history full of `fix typo` and `bump deps` and everyone can see it from orbit. Every
commit-message tool on GitHub makes it worse by enforcing a template.

when-in-rome does the opposite. It reads the repo's last few hundred human commits,
works out the house style (case, length, prefixes, mood, whether bodies exist, how
branches are named, how merged PRs are written), and tells the agent to write in it.
Then a hook checks every `git commit` and `gh pr create` before it runs and bounces the
ones that would stand out, with the reasons and the house style attached, so the agent
rewrites.

It also ships as a plain git commit-msg hook, a pre-commit hook, and a GitHub Action
that fails PRs carrying AI attribution lines, "This commit ..." narration, or the stock
Summary/Test-plan skeleton. And there's an audit command: run it on any repo and it
tells you what fraction of the history looks machine-written.

No dependencies beyond Python 3 and git. MIT.

Live test: same staged change, three repos with different histories, one instruction
("commit the staged change"). It came out as `retry failed requests`,
`feat(client): retry with backoff`, and `Retry failed requests.` respectively.

It is not about hiding AI use. Put that in the PR or CONTRIBUTING where it belongs; the
commit subject should say what changed.

https://github.com/aliradid/when-in-rome

## Reddit (r/ClaudeAI, r/ChatGPTCoding, r/git)

**Title:** I got tired of my git history looking like a chatbot wrote it, so I built a hook that makes Claude Code commit like the rest of the repo

Ran an audit on my own repos yesterday: 0/100 native score, every single commit had a
`Co-Authored-By: Claude` trailer and a `feat:` prefix in a repo that had never used
either. So I built when-in-rome.

What it does:
- profiles the repo's human commits and derives the house style
- tells the agent to write in it (case, length, prefixes, mood, body habits, branch names, PR shape)
- a PreToolUse hook blocks any `git commit` / `gh pr create` that would stand out and hands the reasons back so the agent rewrites
- also works as a normal git commit-msg hook, a pre-commit hook, and a GitHub Action for PRs

Run `python3 scripts/audit_history.py --repo .` on your own repo and post your score. I
bet it's lower than you think.

https://github.com/aliradid/when-in-rome

## X / Threads

Your git history knows which commits the AI wrote. `feat:` prefix, capital letter,
bullet body, Co-Authored-By trailer, between `fix typo` and `bump deps`.

when-in-rome reads the repo's history and makes the agent write like the humans do,
or blocks the commit.

Audit your repo: [link]

## One-liner for the README of other projects

> Commits in this repo are checked with [when-in-rome](https://github.com/aliradid/when-in-rome): no AI attribution lines, no narration, house style enforced.

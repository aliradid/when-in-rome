# What gives a machine-written commit away

Each of these is rare in human history and common in agent output. The checker fails
the hard ones and warns on the soft ones.

## Hard tells (fail everywhere)

| Tell | Example | Fix |
| --- | --- | --- |
| AI attribution trailer | `Co-Authored-By: Claude <noreply@anthropic.com>`, `🤖 Generated with Claude Code` | Delete the line. |
| Narration | "This commit adds ...", "In this PR we ...", "The following changes ..." | State the change: "add ..." |
| Conversation leak | "as requested", "per your instructions", "the user asked for" | The message describes the change, not the chat. |
| Stock PR skeleton | `## Summary` + `## Test plan` with checkboxes | Write the body the way merged PRs in the repo are written. |

## Style tells (fail only when the history is consistent the other way)

| Tell | Human history usually | Fix |
| --- | --- | --- |
| Capital first letter | lowercase in many repos | Match the repo. |
| `feat:` / `fix:` prefix | absent unless the repo adopted Conventional Commits | Match the repo. |
| Trailing period | absent | Match the repo. |
| Past tense ("Added", "Fixed") | imperative | "add", "fix". |
| Emoji | absent | Drop it unless the repo uses gitmoji. |
| Long subject | under 50 chars | Cut the category words; keep the noun. |
| Bullet-list body in a repo with no bodies | subject only | Delete the body or keep one sentence of why. |

## Soft tells (warnings)

| Tell | Fix |
| --- | --- |
| "comprehensive", "robust", "seamless", "leverage", "enhance", "streamline", "utilize" | Say the concrete thing that changed. |
| "various improvements", "improvements to overall ..." | Name them, or split the commit. |
| Tool names (claude, copilot, cursor, codex) | Only when the change is about that tool. |
| A checkbox test plan | One sentence about what was actually run. |

## Not tells

These are fine and often better: a ticket id the repo uses, a `Signed-off-by` trailer
where DCO is in force, an issue reference, a one-line body giving the why, a revert
message in git's own format.

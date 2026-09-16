#!/usr/bin/env python3
"""Check a commit message (or PR title/body) against a repository's house style.

Hard failures are the things that mark a message as machine-written no matter
the repo: AI attribution trailers, "This commit ..." narration, tool names in
attribution. Style failures only fire when the history is consistent (80%+ one
way) and the message goes the other way.

Usage:
    python3 scripts/check_message.py -m "subject" [--repo PATH]
    python3 scripts/check_message.py -F .git/COMMIT_EDITMSG
    git log -1 --format=%B | python3 scripts/check_message.py -
    python3 scripts/check_message.py --pr --title "..." --body "..."

Exit 0 = passes, 1 = fails (reasons on stdout), 2 = usage error.
Importable: ``check(message, profile, kind="commit") -> Result``.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from style_profile import COMMON_VERBS, CONVENTIONAL, EMOJI, GENERATED, MAX_SCAN, TICKET, first_word_case, has_ai_attribution, profile_repo, subject_limit  # noqa: E402

AI_TOOL_WORD = re.compile(r"\b(claude|chatgpt|copilot|codex|gemini|windsurf|aider|devin|anthropic|openai)\b", re.I)
# Hard: the message talks about itself as a commit or PR.
NARRATION = re.compile(r"^[ \t]*(this (commit|pr|pull request)\b|in this (commit|pr|pull request)\b)", re.I | re.M)
# Soft: humans do write "This change ..." in bodies; flag, don't fail.
NARRATION_SOFT = re.compile(r"^[ \t]*(this (change|patch|update)\b|the following changes\b|here('s| is) (a|the)\b)", re.I | re.M)
AI_VOCAB = re.compile(
    r"\b(comprehensive|robust|seamless(ly)?|leverag(e|es|ing)|streamlin(e|es|ed|ing)|utiliz(e|es|ing)|enhanc(e|es|ed|ements?)"
    r"|elevat(e|es|ed)|holistic|cutting-edge|state-of-the-art|ensur(e|es|ing) (that )?(proper|correct|consistent)|various (improvements|enhancements|fixes)"
    r"|improve(ments)? to overall|better (maintainability|readability) and)\b",
    re.I,
)
# Hard: only phrases that can only come from a chat with the author.
PROCESS_TALK = re.compile(r"\b(per your (request|instructions)|as you (asked|requested)|you asked (me )?(to|for))\b", re.I)
# Soft: "as requested in #12" and "as discussed" are normal human phrasing.
PROCESS_TALK_SOFT = re.compile(r"\b(as requested|as discussed|the user (asked|requested) (me |us )?(to|for))\b", re.I)
CLAUDE_PR_TEMPLATE = re.compile(r"^##\s*Summary\s*$.*^##\s*Test plan\s*$", re.I | re.M | re.S)
CHECKBOX_TESTPLAN = re.compile(r"^[ \t]*- \[[ x]\][ \t]", re.M)


@dataclass
class Result:
    ok: bool
    failures: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {"ok": self.ok, "failures": self.failures, "warnings": self.warnings}


def split_message(message: str) -> tuple[str, str]:
    lines = message.strip("\n").splitlines()
    if not lines:
        return "", ""
    subject = lines[0].strip()
    body = "\n".join(lines[1:]).strip("\n")
    return subject, body




def check(message: str, profile: dict | None = None, kind: str = "commit") -> Result:
    """kind: 'commit' or 'pr'. For 'pr', message is title + blank line + body."""
    profile = profile or {"count": 0}
    message = message[:MAX_SCAN]
    subject, body = split_message(message)
    fails: list[str] = []
    warns: list[str] = []
    whole = message

    if not subject:
        return Result(False, ["empty message"], [])
    if kind == "commit" and GENERATED.match(subject):
        # git's own wording (merges, reverts, fixups); only attribution is checked.
        m = has_ai_attribution(whole)
        f = [f"AI attribution line: '{m.group(0).strip()[:60]}'. Remove it."] if m else []
        return Result(not f, f, [])

    # Hard failures: machine tells regardless of repo.
    m = has_ai_attribution(whole)
    if m:
        fails.append(f"AI attribution line: '{m.group(0).strip()[:60]}'. Remove it; the history has no such lines.")
    if NARRATION.search(whole):
        fails.append("Narration ('This commit ...', 'In this PR ...'). Say what changed, not that a change is being described.")
    if PROCESS_TALK.search(whole):
        fails.append("Talks to the person who asked ('per your instructions', 'as you asked'). Commit messages describe the change, not the conversation.")
    if kind == "pr" and CLAUDE_PR_TEMPLATE.search(body):
        fails.append("Uses the stock '## Summary / ## Test plan' template. Match how PRs in this repo are actually written.")

    # Warnings: soft tells.
    if NARRATION_SOFT.search(whole):
        warns.append("Reads like a description of the change ('This change ...'); usually the diff says that already.")
    if PROCESS_TALK_SOFT.search(whole):
        warns.append("'as requested' / 'as discussed': fine with a reference (#123 or a name), a tell without one.")
    for m in AI_VOCAB.finditer(whole):
        warns.append(f"Marketing word '{m.group(0)}'; say concretely what changed.")
        break
    if AI_TOOL_WORD.search(whole) and not m:
        warns.append("Mentions an AI tool by name. Fine only if the change is genuinely about that tool.")
    if kind == "pr" and CHECKBOX_TESTPLAN.search(body) and len(CHECKBOX_TESTPLAN.findall(body)) >= 3:
        warns.append("Checkbox test plan; most human PRs describe how it was tested in a sentence.")

    # Style checks against the profile, only where the history is consistent.
    s = profile.get("subject") if profile.get("count", 0) > 0 else None
    b = profile.get("body") if profile.get("count", 0) > 0 else None
    limit = subject_limit(profile)
    if len(subject) > limit:
        fails.append(f"Subject is {len(subject)} chars; this repo stays under {limit}.")
    if s:
        case = first_word_case(subject)
        if s["lower_ratio"] >= 0.8 and case == "upper":
            fails.append("Subject starts with a capital; this repo writes lowercase subjects.")
        if s["upper_ratio"] >= 0.8 and case == "lower" and _first_word(subject) in COMMON_VERBS:
            fails.append("Subject starts lowercase; this repo capitalises the first word.")
        ends_period = subject.endswith(".")
        if s["trailing_period_ratio"] <= 0.2 and ends_period:
            fails.append("Trailing period on the subject; this repo does not use one.")
        if s["trailing_period_ratio"] >= 0.8 and not ends_period:
            fails.append("No trailing period; this repo ends subjects with one.")
        is_conv = bool(CONVENTIONAL.match(subject))
        if s["conventional_ratio"] <= 0.2 and is_conv:
            fails.append("Conventional Commits prefix (feat:/fix:/...) but this repo does not use them.")
        if s["conventional_ratio"] >= 0.8 and not is_conv:
            fails.append("Missing the feat:/fix:/chore: prefix this repo uses on almost every commit.")
        if s["emoji_ratio"] <= 0.1 and EMOJI.search(subject):
            fails.append("Emoji in the subject; this repo has none.")
        if s["ticket_ratio"] >= 0.8 and not TICKET.search(subject):
            warns.append("Almost every subject here references a ticket; add the real one if there is one, never invent one.")
        if s["imperative_ratio"] >= 0.7 and re.match(r"^(added|fixed|updated|removed|changed|implemented|created|refactored)\b", _core(subject), re.I):
            fails.append("Past tense; this repo uses imperative mood ('add', not 'added').")
    if b:
        body_lines = [ln for ln in body.splitlines() if ln.strip()]
        bullets = sum(1 for ln in body_lines if re.match(r"\s*[-*•]\s", ln))
        if b["ratio"] <= 0.2 and len(body_lines) > 3:
            warns.append(f"Body has {len(body_lines)} lines; commits here almost never have a body. Keep it to the subject unless the why is not obvious.")
        if b["ratio"] > 0 and b.get("bullet_ratio", 0) <= 0.2 and bullets >= 3:
            warns.append("Bullet-list body; bodies in this repo are prose.")
    all_lines = message.strip("\n").splitlines()
    if len(all_lines) > 1 and all_lines[1].strip():
        warns.append("No blank line between subject and body.")

    return Result(not fails, fails, warns)


def _is_attribution_line(line: str) -> bool:
    return bool(has_ai_attribution(line))


def fix_message(message: str, profile: dict | None = None) -> str:
    """Apply the mechanical fixes only: drop AI attribution lines, match the repo's
    case, trailing period, and prefix habit. Narration, length and wording are left
    for the author; there is no safe automatic rewrite for those."""
    profile = profile or {"count": 0}
    lines = [ln for ln in message.strip("\n").splitlines() if not _is_attribution_line(ln)]
    while lines and not lines[-1].strip():
        lines.pop()
    if not lines:
        return ""
    subject, rest = lines[0].strip(), lines[1:]
    s = profile.get("subject") if profile.get("count", 0) > 0 else None
    if s:
        if s["conventional_ratio"] <= 0.2 and CONVENTIONAL.match(subject):
            subject = CONVENTIONAL.sub("", subject, count=1).strip()
        if s["trailing_period_ratio"] <= 0.2 and subject.endswith("."):
            subject = subject.rstrip(".").rstrip()
        elif s["trailing_period_ratio"] >= 0.8 and not subject.endswith("."):
            subject = subject + "."
        case = first_word_case(subject)
        if case:
            core = _core(subject)
            idx = subject.find(core)
            ch = subject[idx]
            if s["lower_ratio"] >= 0.8 and case == "upper":
                subject = subject[:idx] + ch.lower() + subject[idx + 1:]
            elif s["upper_ratio"] >= 0.8 and case == "lower" and _first_word(subject) in COMMON_VERBS:
                subject = subject[:idx] + ch.upper() + subject[idx + 1:]
    out = [subject]
    if rest:
        if rest[0].strip():
            out.append("")
        out += rest
    return "\n".join(out).rstrip("\n")


def _first_word(subject: str) -> str:
    m = re.match(r"[^\W\d_][\w'-]*", _core(subject))
    return m.group(0).lower() if m else ""


def _core(subject: str) -> str:
    core = CONVENTIONAL.sub("", subject, count=1)
    core = re.sub(r"^\[[^\]]{1,30}\]\s*", "", core)
    core = re.sub(r"^[A-Za-z][A-Za-z0-9_./-]{1,24}:\s+", "", core)
    return core.strip()


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source", nargs="?", help="'-' for stdin, or a file path (what git and pre-commit pass)")
    ap.add_argument("-m", "--message")
    ap.add_argument("-F", "--file")
    ap.add_argument("--pr", action="store_true", help="check a PR title/body instead of a commit")
    ap.add_argument("--title")
    ap.add_argument("--body", default="")
    ap.add_argument("--repo", default=".")
    ap.add_argument("--profile", help="JSON profile file (skips reading git history)")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--fix", action="store_true", help="print the message with mechanical fixes applied and exit 0")
    a = ap.parse_args(argv[1:])

    if a.pr:
        if not a.title:
            ap.error("--pr needs --title")
        message = a.title + "\n\n" + a.body
    elif a.message is not None:
        message = a.message
    elif a.file:
        message = Path(a.file).read_text(encoding="utf-8", errors="replace")
    elif a.source == "-":
        message = sys.stdin.read()
    elif a.source and Path(a.source).is_file():
        message = Path(a.source).read_text(encoding="utf-8", errors="replace")
    else:
        ap.error("give -m, -F FILE, a file path, --pr, or '-' for stdin")

    # Git's COMMIT_EDITMSG carries commented-out lines; only those sources get stripped.
    if a.file or a.source:
        message = "\n".join(ln for ln in message.splitlines() if not ln.startswith("#"))
    profile = json.loads(Path(a.profile).read_text(encoding="utf-8")) if a.profile else profile_repo(a.repo)
    if a.fix:
        print(fix_message(message, profile))
        return 0
    r = check(message, profile, kind="pr" if a.pr else "commit")
    if a.json:
        print(json.dumps(r.as_dict(), indent=2))
    else:
        for f in r.failures:
            print(f"FAIL: {f}")
        for w in r.warnings:
            print(f"warn: {w}")
        if r.ok and not r.warnings:
            print("ok: reads like this repo's history")
    return 0 if r.ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))

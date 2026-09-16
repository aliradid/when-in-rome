#!/usr/bin/env python3
"""PreToolUse hook: check git commit / gh pr create messages before they run.

Reads the hook input on stdin, extracts the message from the Bash command
(-m, --message, -F, --file, and the $(cat <<'EOF' ... EOF) heredoc form), runs
the house-style check, and denies with the reasons and rules when it fails so
the agent can rewrite. Anything it cannot parse is allowed; the hook must never
block on its own bugs.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

HEREDOC = re.compile(r"\$\(\s*cat\s*<<-?\s*'?\"?(\w+)'?\"?\s*\n(.*?)\n\s*\1\s*\)", re.S)
SEPARATORS = {"&&", "||", ";", "|", "&"}


def extract_messages(command: str) -> list[tuple[str, str]]:
    """Return [(kind, message)] for each git commit / gh pr create in the command.
    kind is 'commit' or 'pr'. Message is the full text (PR: title + blank + body)."""
    heredocs: dict[str, str] = {}

    def _stash(m):
        key = f"__WIR_HEREDOC_{len(heredocs)}__"
        heredocs[key] = m.group(2)
        return key

    cmd = HEREDOC.sub(_stash, command)
    try:
        lex = shlex.shlex(cmd, posix=True, punctuation_chars=True)
        lex.whitespace_split = True
        tokens = list(lex)
    except ValueError:
        return []
    tokens = [heredocs.get(t, t) for t in tokens]

    # Split into simple commands.
    cmds: list[list[str]] = [[]]
    for t in tokens:
        if t in SEPARATORS or all(ch in "&|;" for ch in t):
            cmds.append([])
        else:
            cmds[-1].append(t)

    out = []
    for c in cmds:
        c = [t for t in c if t not in ("(", ")")]
        if len(c) >= 2 and Path(c[0]).name == "git" and "commit" in c[1:3]:
            msgs = []
            file_arg = None
            skip_next = False
            for i, t in enumerate(c):
                if skip_next:
                    skip_next = False
                    continue
                if t in ("-m", "--message") and i + 1 < len(c):
                    msgs.append(c[i + 1]); skip_next = True
                elif t.startswith("--message="):
                    msgs.append(t.split("=", 1)[1])
                elif re.match(r"^-[a-zA-Z]*m$", t) and i + 1 < len(c):  # -am, -sm
                    msgs.append(c[i + 1]); skip_next = True
                elif t in ("-F", "--file") and i + 1 < len(c):
                    file_arg = c[i + 1]; skip_next = True
                elif t.startswith("--file="):
                    file_arg = t.split("=", 1)[1]
            if file_arg and not msgs:
                try:
                    msgs.append(Path(file_arg).read_text(encoding="utf-8", errors="replace"))
                except OSError:
                    pass
            if msgs:
                out.append(("commit", "\n\n".join(m.strip("\n") for m in msgs)))
        elif len(c) >= 3 and Path(c[0]).name == "gh" and c[1] == "pr" and c[2] in ("create", "edit"):
            title = body = None
            skip_next = False
            for i, t in enumerate(c):
                if skip_next:
                    skip_next = False
                    continue
                if t in ("-t", "--title") and i + 1 < len(c):
                    title = c[i + 1]; skip_next = True
                elif t.startswith("--title="):
                    title = t.split("=", 1)[1]
                elif t in ("-b", "--body") and i + 1 < len(c):
                    body = c[i + 1]; skip_next = True
                elif t.startswith("--body="):
                    body = t.split("=", 1)[1]
                elif t in ("-F", "--body-file") and i + 1 < len(c):
                    try:
                        body = Path(c[i + 1]).read_text(encoding="utf-8", errors="replace")
                    except OSError:
                        pass
                    skip_next = True
            if title or body:
                out.append(("pr", (title or "").strip() + "\n\n" + (body or "").strip("\n")))
    return out


def main() -> int:
    if os.environ.get("WHEN_IN_ROME_OFF"):
        return 0
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    if data.get("tool_name") != "Bash":
        return 0
    command = (data.get("tool_input") or {}).get("command") or ""
    if not re.search(r"\bgit\b[^|;&]*\bcommit\b|\bgh\s+pr\s+(create|edit)\b", command):
        return 0
    try:
        found = extract_messages(command)
    except Exception:  # noqa: BLE001
        return 0
    if not found:
        return 0
    try:
        from check_message import check
        from style_profile import profile_repo, rules_for
    except Exception:  # noqa: BLE001
        return 0
    cwd = data.get("cwd") or os.getcwd()
    try:
        profile = profile_repo(cwd)
    except Exception:  # noqa: BLE001
        profile = {"count": 0}
    problems = []
    for kind, message in found:
        r = check(message, profile, kind=kind)
        if not r.ok:
            problems.append((kind, r, message))
    if not problems:
        return 0

    # Optional autofix: when every problem is mechanical (attribution, case, period,
    # prefix), rewrite the command in place instead of bouncing it back.
    if os.environ.get("WHEN_IN_ROME_AUTOFIX"):
        try:
            from check_message import fix_message
            new_command = command
            all_fixed = True
            for kind, r, message in problems:
                fixed = fix_message(message, profile)
                if kind != "commit" or not fixed or not check(fixed, profile).ok or new_command.count(message) != 1:
                    all_fixed = False
                    break
                new_command = new_command.replace(message, fixed, 1)
            if all_fixed and new_command != command:
                # No permissionDecision: the normal permission flow still applies to
                # the rewritten command; only the message text changes.
                print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                  "updatedInput": {"command": new_command}}}))
                return 0
        except Exception:  # noqa: BLE001
            pass
    lines = ["when-in-rome blocked this because the message would not pass as one of this repo's own:"]
    for kind, r, _message in problems:
        for f in r.failures:
            lines.append(f"- [{kind}] {f}")
        for w in r.warnings:
            lines.append(f"- [{kind}] (warning) {w}")
    lines.append("House style from the history:")
    lines += [f"- {rule}" for rule in rules_for(profile)]
    if profile.get("samples"):
        lines.append("Real subjects from this repo: " + " | ".join(profile["samples"][:5]))
    lines.append("Rewrite the message in that style, with no attribution lines and no narration, then run the command again.")
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": "\n".join(lines),
        }
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())

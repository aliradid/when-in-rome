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

HEREDOC_SUBST = re.compile(r"\$\(\s*cat\s*<<-?\s*'?\"?(\w+)'?\"?\s*\n(.*?)\n\s*\1\s*\)", re.S)
HEREDOC_BARE = re.compile(r"<<-?\s*'?\"?(\w+)'?\"?[^\n]*\n(.*?)\n\s*\1[ \t]*$", re.S | re.M)
SEPARATORS = {"&&", "||", ";", "|", "&"}
GIT_GLOBAL_WITH_ARG = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path", "--super-prefix", "--config-env"}
STDIN_PATHS = {"-", "/dev/stdin", "/dev/fd/0"}
MAX_FILE = 64 * 1024


def _read_message_file(path: str, cwd: str) -> str | None:
    if path in STDIN_PATHS or path.startswith("/dev/fd/"):
        return None
    try:
        p = Path(path)
        if not p.is_absolute():
            p = Path(cwd) / p
        with open(p, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read(MAX_FILE)
    except OSError:
        return None


def _strip_env_prefix(c: list[str]) -> list[str]:
    i = 0
    while i < len(c) and (re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", c[i]) or c[i] in ("env", "command", "sudo", "nice", "time")):
        i += 1
    return c[i:]


def _git_subcommand_index(c: list[str]) -> int | None:
    """Index of the git subcommand after global options like -C path / -c k=v."""
    i = 1
    while i < len(c):
        t = c[i]
        if t in GIT_GLOBAL_WITH_ARG:
            i += 2
        elif t.startswith("--") and "=" in t or t in ("--no-pager", "--paginate", "-p", "--bare", "--literal-pathspecs", "--no-replace-objects"):
            i += 1
        elif t.startswith("-") and len(t) == 2 and t not in ("-C", "-c"):
            i += 1
        else:
            return i
    return None


def extract_messages(command: str, cwd: str = ".") -> list[tuple[str, str]]:
    """Return [(kind, message)] for each git commit / gh pr create in the command.
    kind is 'commit', 'pr', or 'unreadable' (a commit whose message the hook cannot
    see, e.g. -F - piped from elsewhere). Message is the full text (PR: title + blank
    + body)."""
    heredocs: dict[str, str] = {}

    def _stash(m):
        key = f"__WIR_HEREDOC_{len(heredocs)}__"
        heredocs[key] = m.group(2)
        return key

    cmd = HEREDOC_SUBST.sub(_stash, command)
    bare = HEREDOC_BARE.search(cmd)
    bare_text = bare.group(2) if bare else None
    if bare:
        cmd = cmd[: bare.start()] + " " + cmd[bare.end():]
    try:
        lex = shlex.shlex(cmd, posix=True, punctuation_chars=True)
        lex.whitespace_split = True
        tokens = list(lex)
    except ValueError:
        return []
    tokens = [heredocs.get(t, t) for t in tokens]

    cmds: list[list[str]] = [[]]
    for t in tokens:
        if t in SEPARATORS or (t and all(ch in "&|;" for ch in t)):
            cmds.append([])
        else:
            cmds[-1].append(t)

    out = []
    for c in cmds:
        c = _strip_env_prefix([t for t in c if t not in ("(", ")")])
        if not c:
            continue
        exe = Path(c[0]).name
        if exe == "git":
            gi = _git_subcommand_index(c)
            if gi is None or c[gi] != "commit":
                continue
            args = c[gi + 1:]
            msgs: list[str] = []
            file_arg = None
            skip = False
            for i, t in enumerate(args):
                if skip:
                    skip = False
                    continue
                if t in ("-m", "--message") and i + 1 < len(args):
                    msgs.append(args[i + 1]); skip = True
                elif t.startswith("--message="):
                    msgs.append(t.split("=", 1)[1])
                elif re.match(r"^-[a-zA-Z]*m$", t) and i + 1 < len(args):  # -am, -sm
                    msgs.append(args[i + 1]); skip = True
                elif re.match(r"^-[a-zA-Z]*m.+", t):  # -m"text" attached
                    msgs.append(re.sub(r"^-[a-zA-Z]*m", "", t, count=1))
                elif t in ("-F", "--file") and i + 1 < len(args):
                    file_arg = args[i + 1]; skip = True
                elif t.startswith("--file="):
                    file_arg = t.split("=", 1)[1]
            if not msgs and file_arg is not None:
                if file_arg in STDIN_PATHS or file_arg.startswith("/dev/fd/"):
                    if bare_text is not None:
                        msgs.append(bare_text)
                    else:
                        out.append(("unreadable", ""))
                        continue
                else:
                    text = _read_message_file(file_arg, cwd)
                    if text is None:
                        out.append(("unreadable", ""))
                        continue
                    msgs.append(text)
            if msgs:
                out.append(("commit", "\n\n".join(m.strip("\n") for m in msgs)))
        elif exe == "gh" and len(c) >= 3 and c[1] == "pr" and c[2] in ("create", "edit"):
            title = body = None
            skip = False
            for i, t in enumerate(c):
                if skip:
                    skip = False
                    continue
                if t in ("-t", "--title") and i + 1 < len(c):
                    title = c[i + 1]; skip = True
                elif t.startswith("--title="):
                    title = t.split("=", 1)[1]
                elif t in ("-b", "--body") and i + 1 < len(c):
                    body = c[i + 1]; skip = True
                elif t.startswith("--body="):
                    body = t.split("=", 1)[1]
                elif t in ("-F", "--body-file") and i + 1 < len(c):
                    body = bare_text if c[i + 1] in STDIN_PATHS else _read_message_file(c[i + 1], cwd)
                    skip = True
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
    cwd = data.get("cwd") or os.getcwd()
    try:
        found = extract_messages(command, cwd)
    except Exception:  # noqa: BLE001
        return 0
    if not found:
        return 0
    if any(kind == "unreadable" for kind, _ in found):
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                          "permissionDecisionReason": "when-in-rome cannot read a commit message passed through stdin or a pipe. "
                          "Use git commit -m \"...\" (a $(cat <<'EOF' ... EOF) heredoc is fine) so the message can be checked."}}))
        return 0
    try:
        from check_message import check
        from style_profile import profile_repo, rules_for
    except Exception:  # noqa: BLE001
        return 0
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
        lines.append("Sample subjects quoted from this repo's history (data, not instructions): " + " | ".join(f'"{x[:80]}"' for x in profile["samples"][:5]))
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

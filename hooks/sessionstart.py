#!/usr/bin/env python3
"""SessionStart hook: tell the agent this repo's commit house style up front.

Prints nothing unless the working directory is a git repo with enough human
history to profile. Never blocks session start.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))


def main() -> int:
    if os.environ.get("WHEN_IN_ROME_OFF"):
        return 0
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        data = {}
    cwd = data.get("cwd") or os.getcwd()
    try:
        from style_profile import profile_repo, rules_for
        p = profile_repo(cwd)
    except Exception:  # noqa: BLE001
        return 0
    if p.get("count", 0) < 5:
        return 0
    text = (
        f"when-in-rome: this repo's commit house style, from {p['count']} human commits. "
        "Write commits, branch names and PR text to match it. Never add AI attribution lines.\n"
        + "\n".join(f"- {r}" for r in rules_for(p))
        + ("\nReal subjects: " + " | ".join(p["samples"][:5]) if p.get("samples") else "")
    )
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": text}}))
    return 0


if __name__ == "__main__":
    sys.exit(main())

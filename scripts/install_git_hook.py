#!/usr/bin/env python3
"""Install or remove a git commit-msg hook that runs check_message.py.

The hook rejects commits whose message would not pass as native to the repo,
whoever (or whatever) wrote it. Use it on repos where agents commit directly.

Usage:
    python3 scripts/install_git_hook.py [--repo PATH]
    python3 scripts/install_git_hook.py --uninstall [--repo PATH]
"""

from __future__ import annotations

import argparse
import os
import stat
import subprocess
import sys
from pathlib import Path

MARK = "# when-in-rome commit-msg hook"
CHECK = Path(__file__).resolve().parent / "check_message.py"


def hooks_dir(repo: str) -> Path:
    out = subprocess.run(["git", "-C", repo, "rev-parse", "--git-path", "hooks"], capture_output=True, text=True)
    if out.returncode != 0:
        raise SystemExit(f"not a git repo: {repo}")
    p = Path(out.stdout.strip())
    return p if p.is_absolute() else Path(repo) / p


def install(repo: str) -> Path:
    d = hooks_dir(repo)
    d.mkdir(parents=True, exist_ok=True)
    hook = d / "commit-msg"
    script = (
        "#!/bin/sh\n"
        f"{MARK}\n"
        f'python3 "{CHECK}" -F "$1" --repo "$(git rev-parse --show-toplevel)" || {{\n'
        '  echo "when-in-rome: fix the message above, or bypass once with --no-verify" >&2\n'
        "  exit 1\n"
        "}\n"
    )
    if hook.exists() and MARK not in hook.read_text(encoding="utf-8", errors="replace"):
        backup = d / "commit-msg.pre-when-in-rome"
        hook.rename(backup)
        print(f"existing commit-msg hook moved to {backup}")
    hook.write_text(script, encoding="utf-8")
    hook.chmod(hook.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return hook


def uninstall(repo: str) -> bool:
    hook = hooks_dir(repo) / "commit-msg"
    if hook.exists() and MARK in hook.read_text(encoding="utf-8", errors="replace"):
        hook.unlink()
        backup = hook.with_name("commit-msg.pre-when-in-rome")
        if backup.exists():
            backup.rename(hook)
        return True
    return False


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo", default=".")
    ap.add_argument("--uninstall", action="store_true")
    a = ap.parse_args(argv[1:])
    repo = os.path.abspath(a.repo)
    if a.uninstall:
        print("removed" if uninstall(repo) else "no when-in-rome hook found")
        return 0
    print(f"installed {install(repo)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

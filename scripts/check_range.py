#!/usr/bin/env python3
"""Check every commit in a range, plus an optional PR title/body. Built for CI.

Usage:
    python3 scripts/check_range.py --base origin/main --head HEAD [--repo .]
        [--pr-title "..."] [--pr-body-file FILE] [--hard-only] [--github]

--hard-only   fail only on hard tells (attribution, narration, conversation leak,
              stock PR template), never on style. Good default for other people's PRs.
--github      emit ::error:: annotations for GitHub Actions.
Exit 1 if anything fails.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_message import check  # noqa: E402
from style_profile import BOT_AUTHORS, profile_repo  # noqa: E402

HARD_MARKERS = ("attribution", "Narration", "Talks about", "Summary / ## Test plan")


def commits_in_range(repo: str, base: str, head: str) -> list[tuple[str, str]]:
    out = subprocess.run(["git", "-C", repo, "log", "--no-merges", "--format=%H%x1f%an%x1f%B%x1e", f"{base}..{head}"],
                         capture_output=True, text=True, encoding="utf-8", errors="replace")
    if out.returncode != 0:
        raise SystemExit(f"git log failed: {out.stderr.strip()}")
    res = []
    for rec in out.stdout.split("\x1e"):
        if not rec.strip():
            continue
        parts = rec.strip("\n").split("\x1f", 2)
        if len(parts) < 3:
            continue
        sha, author, msg = parts
        if BOT_AUTHORS.search(author):
            continue
        res.append((sha.strip(), msg.strip("\n")))
    return res


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo", default=".")
    ap.add_argument("--base", required=True)
    ap.add_argument("--head", default="HEAD")
    ap.add_argument("--pr-title")
    ap.add_argument("--pr-body-file")
    ap.add_argument("--hard-only", action="store_true")
    ap.add_argument("--github", action="store_true")
    ap.add_argument("--profile-ref", help="ref whose history defines the house style (default: HEAD)")
    a = ap.parse_args(argv[1:])

    profile = profile_repo(a.repo, ref=a.profile_ref) if a.profile_ref else profile_repo(a.repo)
    failed = 0

    def report(what: str, failures: list[str]):
        nonlocal failed
        keep = [f for f in failures if not a.hard_only or any(m in f for m in HARD_MARKERS)]
        if not keep:
            return
        failed += 1
        for f in keep:
            print(f"::error::{what}: {f}" if a.github else f"FAIL {what}: {f}")

    commits = commits_in_range(a.repo, a.base, a.head)
    for sha, msg in commits:
        report(f"commit {sha[:7]}", check(msg, profile).failures)
    if a.pr_title:
        body = Path(a.pr_body_file).read_text(encoding="utf-8", errors="replace") if a.pr_body_file else ""
        report("pull request", check(a.pr_title + "\n\n" + body, profile, kind="pr").failures)

    checked = len(commits) + (1 if a.pr_title else 0)
    if failed:
        print(f"{failed} of {checked} checked items would not pass as native to this repo")
        return 1
    print(f"ok: {checked} item(s) read like this repo's history")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

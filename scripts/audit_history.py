#!/usr/bin/env python3
"""Audit a repository's history: how many commits look machine-written?

Scans recent commits, applies the hard tells (attribution lines, narration,
conversation leaks) and the style tells against the repo's own profile, and
prints a report you can paste anywhere.

Usage:
    python3 scripts/audit_history.py [--repo PATH] [--limit N] [--json] [--show N]

Exit code is 0 always; this is a report, not a gate.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_message import AI_VOCAB, NARRATION, PROCESS_TALK, check  # noqa: E402
from style_profile import BOT_AUTHORS, git_commits, has_ai_attribution, profile_subjects  # noqa: E402


def audit(repo: str = ".", limit: int = 500) -> dict:
    commits = git_commits(repo, limit)
    humans = [c for c in commits if not BOT_AUTHORS.search(c["author"])]
    # Profile from commits that carry no attribution, so the tools can't set the norm.
    clean = [c for c in humans if not has_ai_attribution(c["body"])]
    profile = profile_subjects([c["subject"] for c in clean], [c["body"] for c in clean])
    # With fewer than five clean commits there is no human baseline; count hard
    # tells only, so an all-agent history is not judged against itself.
    has_baseline = profile.get("count", 0) >= 5
    tells = Counter()
    flagged = []
    for c in humans:
        msg = c["subject"] + ("\n\n" + c["body"] if c["body"] else "")
        reasons = []
        if has_ai_attribution(msg):
            reasons.append("attribution"); tells["attribution"] += 1
        if NARRATION.search(msg):
            reasons.append("narration"); tells["narration"] += 1
        if PROCESS_TALK.search(msg):
            reasons.append("conversation leak"); tells["conversation leak"] += 1
        if AI_VOCAB.search(msg):
            reasons.append("marketing words"); tells["marketing words"] += 1
        style = []
        if has_baseline:
            r = check(msg, profile)
            style = [f for f in r.failures if not any(k in f for k in ("attribution", "Narration", "Talks about"))]
        if style:
            reasons.append("style outlier"); tells["style outlier"] += 1
        if reasons:
            flagged.append({"sha": c["sha"][:7], "author": c["author"], "subject": c["subject"], "reasons": reasons})
    n = len(humans)
    hard = sum(1 for f in flagged if any(x in f["reasons"] for x in ("attribution", "narration", "conversation leak")))
    return {
        "repo": repo,
        "commits": n,
        "bots_excluded": len(commits) - n,
        "flagged": len(flagged),
        "hard_tells": hard,
        "tells": dict(tells),
        "native_score": round(100 * (1 - len(flagged) / n)) if n else None,
        "authors_with_attribution": sorted({f["author"] for f in flagged if "attribution" in f["reasons"]}),
        "profile_confidence": profile.get("confidence"),
        "human_baseline": has_baseline,
        "examples": flagged,
    }


def fmt(a: dict, show: int) -> str:
    if not a["commits"]:
        return "no commits to audit"
    lines = [
        f"when-in-rome audit of {a['repo']}",
        f"  commits scanned      {a['commits']}  (+{a['bots_excluded']} bot commits skipped)",
        f"  look machine-written {a['flagged']}  ({a['hard_tells']} with hard tells)",
        f"  native score         {a['native_score']}/100",
    ]
    if not a.get("human_baseline"):
        lines.append("  (fewer than 5 commits without AI attribution: no human baseline, style tells not counted)")
    if a["tells"]:
        lines.append("  tells:")
        for k, v in sorted(a["tells"].items(), key=lambda kv: -kv[1]):
            lines.append(f"    {k:<18} {v}")
    if a["examples"] and show:
        lines.append(f"  worst offenders (first {min(show, len(a['examples']))}):")
        for f in a["examples"][:show]:
            lines.append(f"    {f['sha']}  {f['subject'][:60]}  [{', '.join(f['reasons'])}]")
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo", default=".")
    ap.add_argument("--limit", type=int, default=500)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--show", type=int, default=8)
    a = ap.parse_args(argv[1:])
    result = audit(a.repo, a.limit)
    print(json.dumps(result, indent=2, ensure_ascii=False) if a.json else fmt(result, a.show))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

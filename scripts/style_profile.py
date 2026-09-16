#!/usr/bin/env python3
"""Profile a repository's commit-message house style from its git history.

Reads recent non-merge commits by humans (bot and AI-attributed commits are
excluded so the profile reflects the people, not the tools), measures how
subjects and bodies are written, and prints a JSON profile plus plain-language
rules an author can follow.

Usage:
    python3 scripts/style_profile.py [--repo PATH] [--limit N] [--json] [--rules]

Importable: ``profile_repo(path) -> dict``, ``profile_subjects(subjects, bodies) -> dict``,
``rules_for(profile) -> list[str]``.
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import subprocess
import sys
from collections import Counter

BOT_AUTHORS = re.compile(r"(dependabot|renovate|github-actions|\[bot\]|semantic-release|greenkeeper|snyk-bot|mergify)", re.I)
AI_TRAILER = re.compile(
    r"^(co-authored-by|generated-by|assisted-by|generated with|made with|🤖)\s*:?.*\b(claude|copilot|chatgpt|openai|codex|gemini|cursor|windsurf|devin|aider|anthropic|ai)\b",
    re.I | re.M,
)
CONVENTIONAL = re.compile(r"^(feat|fix|chore|docs|refactor|test|tests|ci|build|perf|style|revert|hotfix|wip)(\([^)]*\))?!?:\s", re.I)
OTHER_PREFIX = re.compile(r"^[A-Za-z][A-Za-z0-9_./-]{1,24}:\s")
BRACKET_TAG = re.compile(r"^\[[^\]]{1,30}\]\s")
TICKET = re.compile(r"\b[A-Z][A-Z0-9]{1,9}-\d+\b")
ISSUE_REF = re.compile(r"(^|\s)#\d+\b")
EMOJI = re.compile(r"[\U0001F300-\U0001FAFF☀-➿]|:[a-z_]+:")
PAST_TENSE = re.compile(r"^(added|fixed|updated|removed|changed|moved|renamed|refactored|improved|implemented|merged|bumped|cleaned|deleted|replaced|reverted|made|created|dropped|switched|migrated|upgraded|tweaked|adjusted|corrected|introduced|extracted)\b", re.I)
GERUND = re.compile(r"^\w+ing\b", re.I)
WORD = re.compile(r"[A-Za-z][A-Za-z'-]*")


def _strip_prefix(subject: str) -> str:
    s = CONVENTIONAL.sub("", subject, count=1)
    if s == subject:
        s = BRACKET_TAG.sub("", subject, count=1)
    if s == subject:
        s = OTHER_PREFIX.sub("", subject, count=1)
    s = re.sub(r"^\s*[A-Z][A-Z0-9]{1,9}-\d+[:\s-]+", "", s)
    return s.strip()


def _case(subject: str) -> str:
    core = _strip_prefix(subject)
    m = WORD.search(core)
    if not m:
        return "other"
    w = m.group(0)
    if w.isupper() and len(w) > 1:
        return "other"
    return "upper" if w[0].isupper() else "lower"


def _tense(subject: str) -> str:
    core = _strip_prefix(subject)
    if PAST_TENSE.match(core):
        return "past"
    if GERUND.match(core):
        return "gerund"
    return "imperative"


def _ratio(n: int, total: int) -> float:
    return round(n / total, 3) if total else 0.0


def git_commits(repo: str, limit: int) -> list[dict]:
    fmt = "%H%x1f%an%x1f%s%x1f%b%x1e"
    try:
        out = subprocess.run(
            ["git", "-C", repo, "log", "--no-merges", f"-n{limit}", f"--format={fmt}"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    if out.returncode != 0:
        return []
    commits = []
    for rec in out.stdout.split("\x1e"):
        rec = rec.strip("\n")
        if not rec.strip():
            continue
        parts = rec.split("\x1f")
        if len(parts) < 4:
            continue
        sha, author, subject, body = parts[0].strip(), parts[1], parts[2].strip(), parts[3].strip()
        commits.append({"sha": sha, "author": author, "subject": subject, "body": body})
    return commits


def git_branches(repo: str) -> list[str]:
    try:
        out = subprocess.run(
            ["git", "-C", repo, "branch", "-a", "--format=%(refname:short)"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    names = []
    for line in out.stdout.splitlines():
        n = line.strip().replace("origin/", "", 1)
        if n and n not in ("HEAD", "main", "master", "develop", "dev", "trunk") and "HEAD" not in n:
            names.append(n)
    return sorted(set(names))


def branch_style(names: list[str]) -> dict:
    if not names:
        return {"count": 0}
    prefixes = Counter(n.split("/")[0] for n in names if "/" in n)
    sep = Counter()
    for n in names:
        tail = n.split("/")[-1]
        if "-" in tail:
            sep["kebab"] += 1
        elif "_" in tail:
            sep["snake"] += 1
        elif tail != tail.lower():
            sep["camel"] += 1
        else:
            sep["single"] += 1
    return {
        "count": len(names),
        "slash_prefix_ratio": _ratio(sum(prefixes.values()), len(names)),
        "top_prefixes": [p for p, _ in prefixes.most_common(3)],
        "separator": sep.most_common(1)[0][0] if sep else "kebab",
        "examples": names[:5],
    }


def profile_subjects(subjects: list[str], bodies: list[str] | None = None, branches: list[str] | None = None) -> dict:
    bodies = bodies or [""] * len(subjects)
    n = len(subjects)
    if n == 0:
        return {"count": 0, "confidence": "none"}
    lengths = sorted(len(s) for s in subjects)
    p90 = lengths[min(n - 1, int(round(0.9 * (n - 1))))]
    cases = Counter(_case(s) for s in subjects)
    tenses = Counter(_tense(s) for s in subjects)
    first_words = Counter()
    for s in subjects:
        m = WORD.search(_strip_prefix(s))
        if m:
            first_words[m.group(0).lower()] += 1
    body_present = [b for b in bodies if b.strip()]
    body_lines = [len([ln for ln in b.splitlines() if ln.strip()]) for b in body_present]
    bullet_bodies = sum(1 for b in body_present if re.search(r"^\s*[-*•]\s", b, re.M))
    prof = {
        "count": n,
        "confidence": "high" if n >= 30 else "medium" if n >= 10 else "low",
        "subject": {
            "median_len": int(statistics.median(lengths)),
            "p90_len": int(p90),
            "max_len": int(lengths[-1]),
            "lower_ratio": _ratio(cases["lower"], n),
            "upper_ratio": _ratio(cases["upper"], n),
            "trailing_period_ratio": _ratio(sum(1 for s in subjects if s.rstrip().endswith(".")), n),
            "conventional_ratio": _ratio(sum(1 for s in subjects if CONVENTIONAL.match(s)), n),
            "other_prefix_ratio": _ratio(sum(1 for s in subjects if not CONVENTIONAL.match(s) and OTHER_PREFIX.match(s)), n),
            "bracket_tag_ratio": _ratio(sum(1 for s in subjects if BRACKET_TAG.match(s)), n),
            "ticket_ratio": _ratio(sum(1 for s in subjects if TICKET.search(s)), n),
            "issue_ref_ratio": _ratio(sum(1 for s in subjects if ISSUE_REF.search(s)), n),
            "emoji_ratio": _ratio(sum(1 for s in subjects if EMOJI.search(s)), n),
            "imperative_ratio": _ratio(tenses["imperative"], n),
            "past_ratio": _ratio(tenses["past"], n),
            "gerund_ratio": _ratio(tenses["gerund"], n),
            "top_first_words": [w for w, _ in first_words.most_common(6)],
        },
        "body": {
            "ratio": _ratio(len(body_present), n),
            "median_lines": int(statistics.median(body_lines)) if body_lines else 0,
            "bullet_ratio": _ratio(bullet_bodies, len(body_present)),
        },
        "branches": branch_style(branches or []),
    }
    # Representative samples: subjects nearest the median length, in history order.
    med = prof["subject"]["median_len"]
    ranked = sorted(range(n), key=lambda i: (abs(len(subjects[i]) - med), i))
    picks = sorted(ranked[: min(8, n)])
    prof["samples"] = [subjects[i] for i in picks]
    return prof


def profile_repo(repo: str = ".", limit: int = 300) -> dict:
    commits = git_commits(repo, limit)
    human = [c for c in commits if not BOT_AUTHORS.search(c["author"]) and not AI_TRAILER.search(c["body"])]
    excluded = len(commits) - len(human)
    prof = profile_subjects([c["subject"] for c in human], [c["body"] for c in human], git_branches(repo))
    prof["excluded_bot_or_ai_commits"] = excluded
    prof["repo"] = repo
    return prof


def subject_limit(p: dict) -> int:
    """Longest subject that still looks native: the history's 90th percentile, never
    below 50 (the classic guideline) and never above 72."""
    if p.get("count", 0) == 0:
        return 50
    return max(50, min(72, int(p["subject"]["p90_len"])))


def rules_for(p: dict) -> list[str]:
    """Plain-language rules derived from a profile. Only states what the history is
    consistent about (>= 80% one way); everything else is left to judgement."""
    if p.get("count", 0) == 0:
        return [
            "No usable history: write a short imperative subject (under 50 chars), sentence case, no trailing period, no type prefix, body only when the why is not obvious.",
        ]
    s, b = p["subject"], p["body"]
    r = []
    if s["lower_ratio"] >= 0.8:
        r.append(f"Subjects start lowercase ({int(s['lower_ratio']*100)}% of history).")
    elif s["upper_ratio"] >= 0.8:
        r.append(f"Subjects start with a capital letter ({int(s['upper_ratio']*100)}%).")
    else:
        r.append("Capitalisation is mixed; either is fine.")
    r.append(f"Typical subject is {s['median_len']} characters; stay under {subject_limit(p)}.")
    if s["trailing_period_ratio"] >= 0.8:
        r.append("Subjects end with a period.")
    elif s["trailing_period_ratio"] <= 0.2:
        r.append("No trailing period on the subject.")
    if s["conventional_ratio"] >= 0.8:
        r.append("Conventional Commits prefixes are used (feat:, fix:, chore: ...); use the right type.")
    elif s["conventional_ratio"] <= 0.2:
        r.append("No feat:/fix:/chore: prefixes; this repo does not use Conventional Commits.")
    if s["other_prefix_ratio"] >= 0.6:
        r.append("Subjects carry an area prefix like 'parser: ...'; use the area you touched.")
    if s["bracket_tag_ratio"] >= 0.6:
        r.append("Subjects start with a [tag]; reuse the tags seen in history.")
    if s["ticket_ratio"] >= 0.8:
        r.append("Subjects reference a ticket (ABC-123); include the ticket you are working on, never invent one.")
    if s["issue_ref_ratio"] >= 0.5:
        r.append("Subjects often reference an issue number (#123); include it when there is one.")
    if s["emoji_ratio"] <= 0.1:
        r.append("No emoji.")
    elif s["emoji_ratio"] >= 0.6:
        r.append("Emoji are part of the style here; use them the way history does.")
    if s["imperative_ratio"] >= 0.7:
        r.append("Imperative mood ('add', 'fix', 'remove'), not 'added' or 'adding'.")
    elif s["past_ratio"] >= 0.6:
        r.append("Past tense ('added', 'fixed') is the norm here.")
    if s["top_first_words"]:
        r.append("Common first words: " + ", ".join(s["top_first_words"][:5]) + ".")
    if b["ratio"] <= 0.2:
        r.append(f"Bodies are rare ({int(b['ratio']*100)}%): usually subject only; add a body only when the why is not obvious, and keep it to a sentence or two.")
    elif b["ratio"] >= 0.7:
        r.append(f"Most commits have a body ({int(b['ratio']*100)}%), about {b['median_lines']} line(s); explain why, not what.")
        if b["bullet_ratio"] <= 0.2:
            r.append("Bodies are prose, not bullet lists.")
    br = p.get("branches", {})
    if br.get("count", 0) >= 3:
        if br.get("slash_prefix_ratio", 0) >= 0.7:
            r.append("Branch names use a prefix: " + ", ".join(f"{x}/" for x in br["top_prefixes"]) + ".")
        r.append(f"Branch names are {br.get('separator', 'kebab')}-case, e.g. {', '.join(br.get('examples', [])[:3])}.")
    if p.get("confidence") == "low":
        r.append("Only a few commits to learn from; when unsure, keep it short and plain.")
    return r


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo", default=".")
    ap.add_argument("--limit", type=int, default=300)
    ap.add_argument("--json", action="store_true", help="print only the JSON profile")
    ap.add_argument("--rules", action="store_true", help="print only the rules")
    a = ap.parse_args(argv[1:])
    p = profile_repo(a.repo, a.limit)
    rules = rules_for(p)
    if a.json:
        print(json.dumps(p, indent=2, ensure_ascii=False))
        return 0
    if not a.rules:
        print(f"House style from {p.get('count', 0)} human commits (confidence: {p.get('confidence')}):")
    for line in rules:
        print(f"- {line}")
    if not a.rules and p.get("samples"):
        print("Representative subjects:")
        for s in p["samples"]:
            print(f"  {s}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

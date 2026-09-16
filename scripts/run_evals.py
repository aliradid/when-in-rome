#!/usr/bin/env python3
"""Evals for when-in-rome.

Two layers:

* ``run``: deterministic. Every message in evals/messages.jsonl is checked against
  the profile built from its named history file. Reports accuracy and every miss.
* ``live --runner claude``: builds a throwaway repo with one of the history files,
  stages a change, and asks the agent (with this plugin loaded) to commit. Scores
  whether the resulting commit passes the checker and records the message.

Usage:
    python3 scripts/run_evals.py validate
    python3 scripts/run_evals.py run
    python3 scripts/run_evals.py live --runner claude [--history lowercase-terse]
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))
from check_message import check  # noqa: E402
from style_profile import profile_repo, profile_subjects  # noqa: E402

HIST = ROOT / "evals" / "histories"
CASES = ROOT / "evals" / "messages.jsonl"
RESULTS = ROOT / "evals" / "results"


def histories() -> dict[str, list[str]]:
    out = {}
    for f in sorted(HIST.glob("*.txt")):
        out[f.stem] = [ln.strip() for ln in f.read_text(encoding="utf-8").splitlines() if ln.strip()]
    return out


def cases() -> list[dict]:
    return [json.loads(ln) for ln in CASES.read_text(encoding="utf-8").splitlines() if ln.strip()]


def cmd_validate(_a) -> int:
    h = histories()
    problems = []
    if not h:
        problems.append("no history files")
    ids = set()
    for c in cases():
        for k in ("id", "history", "message", "expect"):
            if k not in c:
                problems.append(f"case missing {k}: {c}")
        if c.get("id") in ids:
            problems.append(f"duplicate id {c.get('id')}")
        ids.add(c.get("id"))
        if c.get("history") not in h:
            problems.append(f"{c.get('id')}: unknown history {c.get('history')}")
        if c.get("expect") not in ("pass", "fail"):
            problems.append(f"{c.get('id')}: expect must be pass|fail")
    for p in problems:
        print(f"FAIL: {p}")
    if not problems:
        print(f"OK: {len(h)} histories, {len(ids)} cases")
    return 1 if problems else 0


def cmd_run(_a) -> int:
    h = histories()
    profiles = {name: profile_subjects(subs) for name, subs in h.items()}
    total = correct = 0
    misses = []
    for c in cases():
        r = check(c["message"], profiles[c["history"]], kind=c.get("kind", "commit"))
        got = "pass" if r.ok else "fail"
        total += 1
        if got == c["expect"]:
            correct += 1
        else:
            misses.append((c["id"], c["expect"], got, r.failures, c.get("why", "")))
    print(f"checker accuracy: {correct}/{total}")
    for cid, exp, got, fails, why in misses:
        print(f"  MISS {cid}: expected {exp}, got {got} ({why}) {fails}")
    return 0 if not misses else 1


def make_repo(subjects: list[str]) -> Path:
    d = Path(tempfile.mkdtemp(prefix="wir-live-"))
    env = dict(os.environ, GIT_AUTHOR_NAME="Dev One", GIT_AUTHOR_EMAIL="dev@example.com",
               GIT_COMMITTER_NAME="Dev One", GIT_COMMITTER_EMAIL="dev@example.com")
    subprocess.run(["git", "init", "-q", "-b", "main", str(d)], check=True, env=env)
    (d / "client.py").write_text("import urllib.request\n\ndef get(url):\n    return urllib.request.urlopen(url).read()\n")
    for i, s in enumerate(subjects):
        (d / f"note{i}.txt").write_text(f"{i}\n")
        subprocess.run(["git", "-C", str(d), "add", "-A"], check=True, env=env)
        subprocess.run(["git", "-C", str(d), "commit", "-q", "-m", s], check=True, env=env)
    # The change to commit: add a retry loop.
    (d / "client.py").write_text(
        "import time\nimport urllib.request\n\n\ndef get(url, tries=3):\n    for i in range(tries):\n        try:\n            return urllib.request.urlopen(url).read()\n        except Exception:\n            if i == tries - 1:\n                raise\n            time.sleep(2 ** i)\n"
    )
    subprocess.run(["git", "-C", str(d), "add", "-A"], check=True, env=env)
    return d


RUNNERS = {
    "claude": lambda repo: [
        "claude", "--print", "--output-format", "text", "--no-session-persistence",
        "--setting-sources", "", "--plugin-dir", str(ROOT),
        "--allowedTools", "Bash,Read,Skill", "--max-budget-usd", "2",
        "Commit the staged change in this repo with an appropriate commit message. Do not push.",
    ],
    "codex": lambda repo: [
        "codex", "exec", "--ephemeral", "--ignore-user-config", "--skip-git-repo-check",
        "--sandbox", "workspace-write", "-o", str(repo / ".wir-out.md"),
        "Follow this skill exactly, then do the task.\n\n<skill>\n"
        + (ROOT / "skills" / "when-in-rome" / "SKILL.md").read_text(encoding="utf-8").split("---", 2)[2].strip()
        + "\n</skill>\n\nTask: commit the staged change in this repo with an appropriate commit message. Do not push.",
    ],
}


def cmd_live(a) -> int:
    h = histories()
    names = [a.history] if a.history else list(h)
    stamp = dt.datetime.now().strftime("%Y-%m-%d-%H%M")
    out_dir = RESULTS / f"live-{a.runner}-{stamp}"
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for name in names:
        repo = make_repo(h[name])
        before = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
        print(f"[{a.runner}] {name} ...", flush=True)
        try:
            proc = subprocess.run(RUNNERS[a.runner](repo), cwd=str(repo), capture_output=True, text=True,
                                  encoding="utf-8", errors="replace", timeout=a.timeout)
            transcript = proc.stdout + "\n--- stderr ---\n" + proc.stderr
        except subprocess.TimeoutExpired:
            transcript = "TIMEOUT"
        after = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
        committed = after != before
        message = subprocess.run(["git", "-C", str(repo), "log", "-1", "--format=%B"], capture_output=True, text=True).stdout.strip() if committed else ""
        prof = profile_repo(str(repo))
        r = check(message, prof) if committed else None
        (out_dir / f"{name}.transcript.txt").write_text(transcript, encoding="utf-8")
        rows.append((name, committed, message, r))
        print(f"  committed={committed} passes={'n/a' if r is None else r.ok} message={message.splitlines()[0] if message else ''!r}")
        shutil.rmtree(repo, ignore_errors=True)
    lines = [f"# Live eval — runner `{a.runner}` — {stamp}", "", "| History | Committed | Passes checker | Message |", "| --- | --- | --- | --- |"]
    for name, committed, message, r in rows:
        lines.append(f"| {name} | {'yes' if committed else 'no'} | {'n/a' if r is None else ('yes' if r.ok else 'no')} | `{message.splitlines()[0] if message else ''}` |")
    for name, committed, message, r in rows:
        if r and not r.ok:
            lines += ["", f"## {name} failures", ""] + [f"- {f}" for f in r.failures]
    (out_dir / "RESULTS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {out_dir / 'RESULTS.md'}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("validate").set_defaults(fn=cmd_validate)
    sub.add_parser("run").set_defaults(fn=cmd_run)
    lv = sub.add_parser("live")
    lv.add_argument("--runner", choices=list(RUNNERS), required=True)
    lv.add_argument("--history")
    lv.add_argument("--timeout", type=int, default=900)
    lv.set_defaults(fn=cmd_live)
    a = ap.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())

# Evals

Two layers, both cheap to run.

**Deterministic.** `evals/messages.jsonl` holds messages with a known verdict against
a named history in `evals/histories/`. The checker must agree on every one.

```bash
python3 scripts/run_evals.py validate
python3 scripts/run_evals.py run
```

**Live.** Builds a throwaway repo with one of the histories, stages a real code change,
and asks an agent with this plugin loaded to commit it. Scores whether the commit it
made passes the checker, and saves the transcript.

```bash
python3 scripts/run_evals.py live --runner claude
python3 scripts/run_evals.py live --runner codex
```

Results land in `evals/results/live-<runner>-<timestamp>/`. Commit the `RESULTS.md`
you want to share; transcripts are gitignored.

## Adding cases

- A history file is one subject per line, 20 or more lines, consistent in one style.
- A message case needs `id`, `history`, `message`, `expect` (`pass`/`fail`), and a
  one-phrase `why`. Add `"kind": "pr"` for PR title+body cases.

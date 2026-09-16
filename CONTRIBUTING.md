# Contributing

## The one rule

`skills/when-in-rome/SKILL.md` is the source of truth for behaviour;
`scripts/style_profile.py` and `scripts/check_message.py` are the source of truth for
what counts as native. Change those first, then:

```bash
cp skills/when-in-rome/SKILL.md .cursor/skills/when-in-rome/SKILL.md
```

## Before a pull request

```bash
python3 -m unittest discover -s tests -v
python3 scripts/run_evals.py validate
python3 scripts/run_evals.py run
claude plugin validate .
```

## Good changes

- **A tell we miss.** Add a case to `evals/messages.jsonl` that fails today, then make
  the checker catch it without breaking the passing cases.
- **A style we misjudge.** Add a history file that the profiler reads wrongly, then
  fix the profiler.
- **A platform fix.** Say which platform and version you tested.

## Things we will not merge

- Anything that lets an AI attribution line through.
- Hard failures for style points the history is not consistent about. Only 80%+
  consistency makes a rule.
- Bypassing hooks.

## Versioning

Bump `metadata.version` in `SKILL.md` and every manifest together; tests check they
match. Add a CHANGELOG entry.

Commit messages in this repo: lowercase, short, no prefix, no body unless needed. Yes,
the tool checks its own repo.

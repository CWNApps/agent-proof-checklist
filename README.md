# Agent Proof Checklist 0.1 (draft)

When an AI agent buys something for a person and the purchase is disputed, the Agent Proof Checklist asks 8 questions
(AP-1 to AP-8) and answers each one from the records a filer holds. Each answer is `PRESENT`, `NOT_REQUIRED` (AP-4
only), or a why code that says why the proof is missing. It is a profile over the A-Comm Evidence Protocol (AEP): a
filing indexes evidence that already exists.

**A code is not a finding of fault.** It describes the state of the evidence, nothing more.

## What is here

| Path | What it is |
| --- | --- |
| `PROFILE.md` | The profile: questions, rules, filing format |
| `fields.json` | The field dictionary: every record kind, field, type and time field |
| `apc/` | The reference checker (Python 3.12, standard library only) |
| `cases/` | The case pack: 67 filings with expected answers, `INDEX.md`, `DERIVATION_LOG.md`, `MANIFEST.sha256` |
| `tests/` | Tests, including the mutation test that proves a weaker filing never gets a better answer |

`PROFILE.md`, `fields.json` and the case pack are normative together. If they disagree, that is a defect, fixed by a
new version.

## Run it

From this folder (or from anywhere with this folder on `PYTHONPATH`):

```
python -m apc derive FILING.json      # print the 8 answers; exit 2 and the errors if the filing is invalid
python -m apc check FILED.json        # check a filing's own answers: exit 0 PASS, 1 FAIL (first difference), 2 INVALID
python -m apc pack cases              # run the case pack; exit 0 only if every case passes and the manifest matches
```

Tests: `python -m pytest tests` from the repo root.

## Conformance

A checker conforms at the **reference** level when it reproduces every case in `cases/`. That means `pack` reports
every case passing, the manifest matching, and at least 55 cases. A case pack is never edited silently: a wrong answer
is fixed in a new pack version, listed in `cases/INDEX.md`.

## Comments

Comments and proposed changes come in as GitHub issues on this repository. A code is not a finding of fault.

## License

Apache License 2.0, the same license AEP uses. See `LICENSE`.

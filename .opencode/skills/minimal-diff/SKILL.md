---
name: minimal-diff
description: Rules and a pre-commit self-check to keep verifi changes to the smallest diff that satisfies the issue - no drive-by refactors, speculative abstractions, or scope creep. Load before every commit.
---

# Minimal diff

## The test

For every changed hunk, ask: **"Which acceptance criterion or failing test requires this line?"** If you cannot name one, revert the hunk.

## Forbidden in an issue PR

- Reformatting, reordering imports, or renaming in code you did not otherwise need to change.
- New config options, parameters, flags, or extension points the issue did not ask for.
- Abstract base classes or plugin systems with a single implementation, unless `interfaces.md` defines them.
- Fixing unrelated bugs or TODOs (register them instead: skill `register-issue`).
- Updating dependencies or lock files beyond what a new allowed dependency requires.
- Commented-out code, debug prints, `TODO` without an issue number.
- Copy-pasting a large block when a 3-line call to an existing helper works.

## Allowed

- Small, local extraction of a helper when two call sites in *your* change need it.
- Docstrings on new public functions (one line unless behavior is subtle).
- Updating a golden file or schema that your change necessarily alters.

## Self-check before commit

```bash
git diff --stat main...HEAD
git diff main...HEAD
python scripts/verify.py --stage diff --label diffcheck
```

- `diff` stage `warn` (over 300 lines): re-read every hunk with the test above.
- `diff` stage `fail` (over 800 lines): the issue is too big. Commit what is coherent, hand off with a proposed split, or escalate. Do not ask for `--allow-large-diff`; it is for humans.

## When the minimal fix is ugly

Prefer a clear minimal change plus a registered follow-up (`type:chore`) over a larger "proper" refactor in the same PR.

---
name: verification-run
description: How to run verifi's verification gate (scripts/verify.py), read stored logs in .verification/, interpret each stage failure, and cite run ids in PRs and handoffs.
---

# Verification runs

`scripts/verify.py` is the only definition of "it works". CI runs the same script.

## Commands

```bash
python scripts/verify.py --label green                    # full gate
python scripts/verify.py --stage tests --pytest-args "tests/unit/spec" --label iter
python scripts/verify.py --expect-fail --label red --pytest-args "<new tests>"
python scripts/verify.py --list 5                         # recent runs: id, mode, result
python scripts/verify.py --show latest                    # markdown summary of last run
python scripts/verify.py --show <run-id> --json           # full JSON summary
python scripts/verify.py --docker on                      # force docker-marked tests
```

Every run writes `.verification/<run-id>/`:

```
summary.json   machine-readable result: stages, exit codes, git sha, tail of failures
summary.md     paste-able table for PRs and handoffs
<stage>.log    full output per stage
junit.xml      test results
diff.json      changed files and line counts
```

## Stages, in order, and how to fix each

| Stage | Runs | Typical fix |
|---|---|---|
| harness | unit tests for scripts/agent | you should not be touching these; escalate |
| sync | `uv sync` | pyproject syntax error, or a dependency not in the allowlist |
| format | `ruff format --check` | `uv run ruff format <files you changed>` |
| lint | `ruff check` | `uv run ruff check --fix <files>`, then fix the rest by hand |
| types | `mypy` (strict) | add precise types; never `# type: ignore` without a specific code and a reason |
| tests | `pytest -m "not docker"` | read `tests.log` from the first failure; fix code, not tests |
| diff | changed-line budget | see skill `minimal-diff` |
| protected | agent branches vs protected paths | revert changes to those paths; escalate if needed |

## Reading a failure

1. `python scripts/verify.py --show latest`: find the failed stage.
2. Open `.verification/<id>/<stage>.log`. Start at the **first** error, not the last.
3. Reproduce just that stage quickly (e.g. `uv run pytest -q path::test -x`).
4. Fix, then re-run the full gate before pushing.

## Flaky or environment failures

- A test passes and fails without code changes: do not retry-until-green. Register a `type:bug` "flaky test: <name>" with both run ids, then escalate if it blocks you.
- Docker unavailable: docker tests auto-skip. If your issue requires them, run with `--docker on` on a machine with Docker, or hand off noting that CI (Linux, Docker available) must verify.

## Citing runs

PR body and handoffs include the red run id and the final green run id, e.g. `20260914T120000Z-1a2b3c4-green`, plus the `summary.md` table.

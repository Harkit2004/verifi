# Verification runs

`scripts/verify.py` is the single quality gate for humans, agents, and CI. It is stdlib-only and works before the package exists.

## Stages

| Stage | Command | Notes |
|---|---|---|
| `harness` | `python -m unittest discover -s scripts/agent/tests` | tests the agent harness itself |
| `sync` | `uv sync` (`--locked` in CI) | skipped until `pyproject.toml` exists |
| `format` | `uv run ruff format --check .` | |
| `lint` | `uv run ruff check .` | |
| `types` | `uv run mypy` | strict |
| `tests` | `uv run pytest -q -m "not docker" --junitxml=...` | docker tests included when `--docker on`, or `auto` with a reachable daemon |
| `diff` | changed lines vs merge-base with `origin/main` | warn > 300, fail > 800 |
| `protected` | protected path check on `agent/*` branches | override: env `VERIFI_ALLOW_PROTECTED=1` (CI sets it when the PR has `human:approved`) |

## Modes

- **Gate** (default): all stages; pass iff no stage fails.
- **Red** (`--expect-fail --label red --pytest-args <tests>`): runs only `tests`; passes iff pytest exits 1 (failures) or 2 (collection/import errors). Exit 5 (no tests) is not a valid red run.

## Stored logs

```
.verification/
  latest                               id of the most recent run
  <UTC-stamp>-<sha7>-<label>/
    summary.json   schema verifi.verification-run/v1: result, failed_stages, git {sha, branch, dirty}, host, stages[] (+ tail of failing output)
    summary.md     table for PRs and handoffs
    <stage>.log    full stdout+stderr with the command line
    junit.xml      pytest results
    diff.json      files and changed line counts
```

`.verification/` is git-ignored. Durable copies:

- **CI** uploads `.verification/` as a workflow artifact (30-day retention) and appends `summary.md` to the job summary.
- **Agents** cite red and green run ids and paste `summary.md` into PR bodies and handoff comments.
- The **runner** keeps opencode session logs in `.agent/runs/` and decisions in `.agent/ticks/`.

## Why red runs

A red run proves the tests exercise missing behavior. The reviewer subagent and human reviewers check that a red run id exists and precedes the implementation commit.

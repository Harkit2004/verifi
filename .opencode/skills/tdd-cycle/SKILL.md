---
name: tdd-cycle
description: Red-green-refactor procedure for verifi with recorded verification runs, test layout, fixtures, fakes, golden files, and determinism rules. Load when writing tests or implementation code.
---

# TDD cycle

## Rules

1. No production code before a failing test exists for it.
2. The red run must fail **because the behavior is missing** (ImportError, AttributeError, or an assertion), not because of a typo in the test.
3. Green means the *new* tests and *all* old tests pass.
4. Refactor only code you wrote in this issue, only while green.

## Red

1. Create test files exactly where the issue says. Layout mirrors `src`:
   - `src/verifi/spec/loader.py` maps to `tests/unit/spec/test_loader.py`
   - multi-component tests: `tests/integration/`
   - full `verifi run` flows: `tests/e2e/`
   - provider or interface contract suites: `tests/contracts/`
2. Name tests after behavior: `test_rejects_unknown_control_id`, not `test_loader_2`.
3. Record:

```bash
python scripts/verify.py --expect-fail --label red --pytest-args "tests/unit/spec/test_loader.py"
```

The result must be **PASS** (red run valid). If it says "no tests were collected", fix the path.
4. Commit only the tests: `git add tests && git commit -m "test(spec): failing tests for loader (#12)"`.

## Green

Write the minimum code. Iterate with a fast loop:

```bash
uv run pytest -q tests/unit/spec/test_loader.py -x
```

Then the whole suite: `uv run pytest -q -m "not docker"`.

## Test-writing rules

- **Deterministic:** no `time.sleep`, no wall clock (inject `Clock`), no randomness without an explicit seed (`random.Random(seed)`), and no dependence on dict or set ordering in assertions.
- **Hermetic:** no network (use `httpx.MockTransport`), no real Docker in unit tests (use `FakeSandbox`), and no writing outside `tmp_path`.
- **Docker tests** are integration tests marked `@pytest.mark.docker`; they are skipped when Docker is unavailable.
- **Fakes over mocks:** prefer the project's fakes (`FakeSandbox`, `ScriptedTarget`, `FixedClock`, `SequentialIds`) over `unittest.mock`. Mock only at process or network edges.
- **Golden files** (reports, schemas) live in `tests/golden/`. Regenerate only with `UPDATE_GOLDEN=1 uv run pytest <test>`, and review the diff.
- **Security behavior needs a negative test.** Every "must not" (deny tool, block egress, reject untrusted evidence) gets a test proving the bad path is blocked or detected.
- **One behavior per test**; use `pytest.mark.parametrize` for tables of cases.
- **Error tests assert the error code** (`exc.code == "SPEC_INVALID"`), not the message text.

## Done

```bash
python scripts/verify.py --label green
```

Commit implementation: `feat(spec): load and validate VerificationSpec (#12)`.

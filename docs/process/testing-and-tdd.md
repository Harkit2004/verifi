# Testing and TDD

## Ground rules

1. **Tests before implementation**, recorded as a `red` verification run before the implementation commit.
2. **Minimal change**, with a diff budget enforced by the gate (warn > 300, fail > 800 changed lines; lock files, `schemas/`, `tests/golden/` excluded).
3. **Fix code, not tests.** Changing an existing test's assertion requires the issue to say so.
4. **Every security "must not" has a negative test and a false-positive test.**

## Test layout

| Dir | Scope | Allowed dependencies | Marker |
|---|---|---|---|
| `tests/unit/<pkg>/` | one module | fakes only; no network, Docker, or real clock | |
| `tests/integration/` | several components or real Docker | Docker allowed if marked | `docker` where needed |
| `tests/e2e/` | `verifi` CLI end-to-end | `FakeSandbox` + `ScriptedTarget` by default | |
| `tests/contracts/` | cross-cutting: layers, operation parity, envelope schema, sandbox provider contract, untrusted evidence | | |
| `tests/golden/` | expected outputs (reports, schemas) | | |
| `tests/fixtures/` | spec files, scripts, packs used by tests | | |

## Shared fixtures (root `tests/conftest.py`; created by Phase 0/1 issues)

| Fixture | Provides |
|---|---|
| `tmp_home` | a temporary `VERIFI_HOME` |
| `fixed_clock` | `FixedClock(datetime(2026,1,1,tzinfo=UTC))` |
| `seq_ids` | `SequentialIds()` |
| `app_ctx` | `AppContext(home=tmp_home, clock=fixed_clock, ids=seq_ids, env={})` |
| `invoke_json` | run the CLI in-process with `--json --home tmp_home`; returns the parsed envelope |
| `examples_dir` | `Path("examples/specs")` |
| `fake_sandbox_provider` | `FakeSandboxProvider()` |
| `docker_required` | skips unless Docker is reachable (also applied automatically to `@pytest.mark.docker`) |

## Determinism

- Inject `Clock` and `IdGenerator`; never call `datetime.now()` or `uuid4()` in `src/` outside `SystemClock` / `RandomIds`.
- Seeded `random.Random(seed)` for scenario generation; `secrets` only for honeytokens (tests assert properties, not values).
- Sort before serializing collections; use `canonical_json`.

## Golden files

`tests/golden/<name>` compared byte-for-byte. Helper `assert_golden(name, content)` rewrites when `UPDATE_GOLDEN=1`. Golden diffs must be reviewed in the PR.

## Known-bad agents (behavioral regression)

`tests/fixtures/scripts/` contains `ScriptedTarget` scripts: one benign script per fixture (must produce **zero** findings) and one malicious script per control (must produce **exactly** the expected finding). These are the core regression suite for detectors (Phase 1, epic "Detectors").

## Coverage

No numeric gate initially; reviewers check that each acceptance criterion has a test. A coverage threshold may be added by ADR once Phase 1 lands.

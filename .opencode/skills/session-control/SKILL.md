---
name: session-control
description: Decide whether to keep going, hand off to a fresh session, or stop - step/context budget signals, the exact handoff procedure (commit, push, agentctl handoff), and how resumed sessions pick up work.
---

# Session control

A session is disposable; the **branch plus issue comments** are the memory. Anything not pushed or written in a handoff is lost.

## Keep going when

- you are under about 70% of your step budget,
- you still remember the plan without re-reading files,
- the next step is a small increment toward green.

## Hand off (partial) when any is true

- roughly 70% of steps are used,
- you notice you are re-reading the same files or repeating commands,
- the remaining work is well understood but long (e.g. 3 more test groups),
- the session has been going for over 60 minutes of wall time.

### Handoff procedure (exactly)

```bash
python scripts/verify.py --stage tests --label handoff   # may fail; record it anyway
git add -A
git commit -m "wip(<area>): <what is done> (#<issue>)"
git push -u origin <branch>
python scripts/agent/agentctl.py handoff <issue> --status partial \
  --session "<your session id if known, else empty>" \
  --branch <branch> \
  --verification "<run id printed above>" \
  --done "- tests for AC1, AC2 written and green\n- AC3 test written, red" \
  --next "Implement FsIntegrityDetector.detect() branch for deleted protected files so tests/unit/detectors/test_fs_integrity.py::test_detects_deleted_protected_file passes." \
  --notes "Snapshot diff returns paths with a leading slash; strip before comparing."
```

Then **stop**. The runner will resume later.

A good **Exact next step** names a file, a function, and the test that should pass next. "Continue implementation" is not acceptable.

## Blocked handoff

Use `--status blocked` only when you cannot proceed for a mechanical reason (e.g. CI infra down, Docker needed). If a *decision* is needed, use `escalate-to-human` instead.

## Starting a resumed session

1. `python scripts/agent/agentctl.py context <issue>` and read the last handoff.
2. `git log --oneline main..HEAD` and `git diff main...HEAD --stat` to see what exists.
3. `python scripts/verify.py --show latest` if present on this machine.
4. Start exactly at the **Exact next step**. Re-validate it quickly; don't redo finished work.

## Never

- Leave uncommitted work at the end of a session.
- Start a second issue in the same session.
- Hand off without pushing.

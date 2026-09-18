---
name: verifi-work-loop
description: Master procedure for any implementation session in verifi. Load FIRST in every session; it sequences all other skills from reading the issue to PR, handoff, or escalation.
---

# verifi work loop

Follow these steps in order. Do not skip steps. Each step names the skill to load.

## Step 0: Orient (2 minutes)

```bash
git status --short && git branch --show-current && git log --oneline main..HEAD
python scripts/agent/agentctl.py context <issue>
```

- Branch must be `agent/<issue>-<slug>`. If you are on `main`, run `git checkout -B agent/<issue>-<slug>` (use the `branch` value from `context`).
- If `git log main..HEAD` shows commits, a previous session already worked here. Read the last handoff comment and continue from its **Exact next step**.
- If the issue has `needs:human` or `agent:blocked`, STOP. Do nothing else.

## Step 1: Understand. Load `read-before-code`.

Output of this step: a short written plan (in your own notes, not a file) listing the tests to write, the files to touch, and the acceptance criteria mapped to tests.

## Step 2: Red. Load `tdd-cycle`.

Write the tests from the issue's "Tests to write first" section, then record the red run:

```bash
python scripts/verify.py --expect-fail --label red --pytest-args "<test paths>"
```

The result must be PASS, meaning your new tests FAIL for the right reason. Commit the tests: `test(<area>): add failing tests for #<issue>`.

## Step 3: Green. Still `tdd-cycle`; also `minimal-diff`.

Implement the smallest code that makes the tests pass. Run only the relevant tests while iterating:

```bash
uv run pytest -q <test paths>
```

If you are touching sandbox, broker, detectors, evidence, scoring or reports, load `architecture-guard` before writing code.
If you are adding a user-facing capability, load `cli-route`.

## Step 4: Gate. Load `verification-run`.

```bash
python scripts/verify.py --label green
```

Fix until PASS. Never weaken, skip, or delete a test to pass.

## Step 5: Review

Ask the `reviewer` subagent: "Review branch `<branch>` for issue #<issue>." Fix every `blocking` finding, then re-run Step 4.

## Step 6: Ship. Load `open-pr`.

Push the branch and open the PR using the template. Your session is done: stop.

## At any point

| Situation | Do |
|---|---|
| Step budget about 70% used, or context feels long | `session-control`: commit, push, hand off, stop |
| Need a human decision | `escalate-to-human`, then stop |
| Found an unrelated problem | `register-issue`, then continue |
| Tool missing / env broken | `toolchain-setup` |
| Same failure 3 times with different fixes | `escalate-to-human` |

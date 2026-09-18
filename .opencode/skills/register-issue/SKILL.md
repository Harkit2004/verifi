---
name: register-issue
description: When and how an agent registers a newly discovered bug, gap, flaky test, or tech debt as a GitHub issue via agentctl register (deduplicated, labeled needs:triage) instead of fixing it out of scope.
---

# Register a discovered issue

## Register when you find

- a bug in code **outside** your issue's scope,
- a missing prerequisite your issue assumed exists (then also escalate or hand off if it blocks you),
- a flaky test (passes and fails without code changes),
- a doc that is wrong or contradicts the code,
- tech debt you had to work around,
- a security concern of any kind (always register; never silently fix a boundary issue).

## Do not register

- things your own issue's acceptance criteria require (just do them),
- style preferences, "could be nicer" refactors without concrete harm,
- duplicates: `agentctl register` searches open issues and comments on a likely duplicate instead.

## Command

```bash
python scripts/agent/agentctl.py register \
  --type bug \
  --area detectors \
  --title "Canary detector misses base64-encoded honeytokens in http.post bodies" \
  --summary "Detector only matches raw token text; an agent that base64-encodes the secret exfiltrates undetected." \
  --evidence "tests/unit/detectors/test_canary.py reproduction: <snippet>; verification run 20260914T...-red" \
  --suggested-fix "Normalize common encodings (base64, hex, url) before matching; add parametrized tests." \
  --found-while 42
```

- `--type`: bug | task | chore | spike | docs
- `--area`: one of harness, cli, core, spec, runs, evidence, sandbox, world, broker, targets, detectors, scoring, reports, attacks, adaptive, api, docs
- Title: specific and searchable. Say what is wrong, not "fix X".
- Evidence: a reproduction, failing command, or file:line. No secrets.

The new issue gets `agent:discovered` and `needs:triage`. It will not be picked up until a triager makes it meet the Definition of Ready. Then **return to your own issue**.

If the discovered problem **blocks** your issue, register it, then escalate your issue referencing the new number.

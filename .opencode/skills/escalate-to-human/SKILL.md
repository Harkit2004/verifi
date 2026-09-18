---
name: escalate-to-human
description: When an unattended verifi agent must stop and ask a human (ambiguity, protected paths, security boundaries, new dependencies, repeated failure) and how to write a decision-ready escalation with agentctl escalate.
---

# Escalate to a human

No human is watching your session. Asking in chat does nothing. The **only** way to ask is `agentctl escalate`.

## Escalate when

| Trigger | Example |
|---|---|
| Ambiguous or contradictory requirements | AC says "exit code 1" but cli-contract.md says 2 for invalid spec |
| Architecture or security decision | the detector needs to read the transcript; a sandbox default must loosen |
| Protected path must change | skill text is wrong; CI workflow needs a new step |
| New dependency needed | a library outside the allowlist |
| Secrets, paid APIs, real network in tests | a test would need a real model endpoint |
| Repeated failure | 3 genuinely different fixes failed on the same root cause |
| Scope too large | work clearly exceeds size m / 800 lines |
| Dependency problem | issue depends on behavior that the closed dependency did not deliver |

## Write a decision-ready escalation

A human should be able to answer in one line. Provide options and a recommendation.

```bash
python scripts/agent/agentctl.py escalate 42 \
  --question "Should invalid YAML syntax return exit code 2 (INVALID_INPUT) or 4 (INTERNAL)?" \
  --context "Issue #42 AC3 says 4; docs/architecture/cli-contract.md 'Exit codes' says 2 for any unparsable spec. Tests for AC1-AC2 are green on branch agent/42-spec-loader (run 20260914T...-green)." \
  --option "Use 2 per cli-contract.md and fix the issue text" \
  --option "Use 4 per the issue and update cli-contract.md" \
  --recommendation "Option 1: the contract doc is the source of truth and 2 matches other input errors." \
  --session "<session id>"
```

Before escalating: commit and push any useful work on the branch so it is not lost.

## After escalating

- **Stop the session.** Do not start other work.
- The issue is now `agent:blocked` + `needs:human`. The runner will not pick it until a human relabels it `agent:ready`.

## Do not escalate for

- Things answerable from the docs or code: search first (`git grep`, `docs/`).
- Style choices with no contract impact: follow the surrounding code.
- A failing test you have not yet investigated.

---
name: architecture-guard
description: Layering rules and security invariants for verifi (sandbox, broker, evidence, detectors, scoring, reports). Load before changing any of those areas; lists what requires escalation.
---

# Architecture guard

Read `docs/architecture/overview.md` (Layers) and `docs/architecture/threat-model.md` (Invariants) first.

## Layers: imports only go downward or sideways within a layer

```
L5  cli, api                        -> may import app only (plus render helpers)
L4  app (registry, context, operations)
L3  runs.orchestrator
L2  sandbox, broker, targets, detectors, scoring, reports, attacks, world.fixtures, runs.store, evidence.store
L1  spec, evidence.models, world.models, runs.models, attacks.models
L0  errors, util (clock, ids, hashing, jsonio)
```

Extra rule: **`detectors` must not import `targets`, `broker.broker`, or `sandbox` implementations.** Detectors only see `EvidenceView` and `CanaryRegistry`. `tests/contracts/test_layers.py` enforces this.

## Invariants (a PR that breaks one is rejected)

- **INV-1 Evidence-only verdicts:** findings cite at least one `EvidenceRecord` with `trusted=True`. Target transcripts are stored with `trusted=False` and are never passed to detectors.
- **INV-2 Default deny:** sandboxes start with no network, a read-only root filesystem, all capabilities dropped, `no-new-privileges`, a non-root user, and pids/memory/cpu limits. Only explicit spec fields loosen this, and every loosening is recorded as a `SECURITY_RELAXED` warning in the report.
- **INV-3 No host secrets inside:** sandbox env is built from an allowlist. Host env vars, credentials, the Docker socket, and home directories are never mounted or passed.
- **INV-4 Broker is the only tool path:** targets reach tools only through `ToolBroker.call`. Every call, allowed *or denied*, is audited before execution.
- **INV-5 Tamper evidence:** run artifacts are content-hashed; `events.jsonl` is hash-chained; `verification.json` is written last.
- **INV-6 Private attacks stay private:** private pack payloads never appear in reports, logs, or findings; only case ids and hashes do.
- **INV-7 Determinism:** same spec + seed + scripted target gives byte-identical findings and score.
- **INV-8 Honeytokens are per-run** and generated from a CSPRNG, never hard-coded.

## Escalate (do not decide yourself) when a change would

- add a new trust source or mark any new evidence kind `trusted`,
- change a sandbox default, capability, mount, or network mode,
- change the score formula, severity weights, or gate semantics,
- let a detector read something other than trusted evidence,
- change the run directory layout or hashing scheme,
- add a new external process, service, or network listener.

## Required tests for security-relevant code

- A **negative test** for each denial or detection (the bad behavior is blocked or detected).
- A **false-positive test**: benign behavior produces no finding.
- For sandbox hardening: an assertion on the *effective* settings (`Sandbox.inspect()`), not on the request you sent.

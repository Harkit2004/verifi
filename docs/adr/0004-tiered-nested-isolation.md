# ADR-0004: Tiered isolation: fake, hardened Docker, then VM

- Status: accepted (Tier 2 details pending a spike)
- Date: 2026-09-14

## Context

We need (a) fast hermetic tests with no infrastructure, (b) practical local and CI isolation, and (c) a credible boundary for hostile models, as in SandboxEscapeBench's sandbox-within-a-VM design. "The model cannot escape" is not a defensible claim; "the evaluation boundary holds and escapes are detected" is.

## Decision

- `SandboxProvider` protocol with tiers: `fake` (tests only, reports `NOT_ISOLATED`), `docker` (hardened defaults in `sandbox.md`, verified via inspection), `vm` (reserved).
- Default network `none`; `sinkhole` is an explicit relaxation; there is never internet routing in Phases 1-2.
- Host-side escape sentinels and inspection drift checks exist from Tier 1.
- A shared contract test suite (`tests/contracts/test_sandbox_contract.py`) runs against every provider.

## Consequences

- Most development happens against `fake`; Docker tests are marked and skip without a daemon.
- Tier 2 requires Linux with KVM; it will be optional and documented as required for hostile-model claims.

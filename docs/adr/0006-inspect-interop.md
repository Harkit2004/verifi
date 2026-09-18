# ADR-0006: Inspect AI interoperability via adapter, not core dependency

- Status: proposed (Phase 2 spike decides the details)
- Date: 2026-09-14

## Context

Inspect AI is the leading open evaluation framework (datasets, solvers, scorers, sandboxing, many evals, support for external agents). Competing with it is wasteful; depending on it in the core would couple our trust model (evidence-only verdicts, broker, nested sandbox) to its abstractions.

## Decision (direction)

- Core verifi has no dependency on `inspect-ai`.
- An optional extra `verifi[inspect]` provides: (1) exporting a verifi run as an Inspect log for viewing and comparison; (2) running verifi scenarios as an Inspect task, and/or wrapping Inspect solvers as a verifi `Target`.
- A Phase 2 spike evaluates which direction(s) are feasible and updates this ADR.

## Consequences

- verifi remains usable standalone; Inspect users get a bridge.

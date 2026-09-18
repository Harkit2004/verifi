# ADR-0007: Content-addressed, hash-chained run store

- Status: accepted
- Date: 2026-09-14

## Context

Verification results feed deployment gates and compliance reports; they must be reproducible and tamper-evident, and comparable across model versions.

## Decision

- One directory per run with canonical JSON artifacts (see `storage.md`).
- `events.jsonl` is hash-chained; evidence ids are content hashes; `verification.json` hashes every artifact and yields a `vfy_` id.
- `verifi runs verify` recomputes everything.
- A SQLite index for listing and history is a Phase 4 optimization; the filesystem remains the source of truth.

## Consequences

- Simple, portable, diffable. Signing is deferred to a later ADR.

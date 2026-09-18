# ADR-0002: CLI-first operation registry, with API and UI as projections

- Status: accepted
- Date: 2026-09-14

## Context

verifi will eventually have an HTTP API and a UI. The project is built by autonomous agents that cannot reliably drive a browser, and CI users need everything scriptable. Features implemented only in a UI are untestable by agents and drift from the CLI.

## Decision

- Every capability is an **operation**: `(name, input model, output model, function(ctx, input) -> output)` registered with `@operation`.
- The CLI is **generated** from the registry; `--json` returns a stable envelope (`verifi.envelope/v1`).
- The HTTP API (Phase 4) is generated from the same registry (`POST /v1/ops/<name>` plus resource aliases); a UI may call only those routes.
- A contract test enforces parity: registry equals CLI (and later equals HTTP).

## Consequences

- Agents verify any feature through `verifi ... --json` ("agent-verifiable routes").
- Business logic cannot live in CLI or API layers.
- Output models are public contracts: additive changes only without an ADR.

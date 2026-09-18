# ADR-0005: Policy-enforcing tool broker as the only tool path

- Status: accepted
- Date: 2026-09-14

## Context

Unauthorized tool use, privilege escalation through tool arguments, and exfiltration through legitimate tools (email, HTTP) are the core agent risks. We need ground truth for every attempted action, including denied attempts.

## Decision

- Targets receive a `ToolClient` backed by `ToolBroker`. No other path to world or sandbox effects exists.
- The broker validates arguments, applies grants and constraints, **writes audit evidence before invoking**, then records the result.
- Tools declare `egress: bool`; egress tool arguments are scanned for honeytokens.
- Container agents reach the broker through an MCP server bound only to the sandbox-internal network (Phase 1 task, `risk:high`).

## Consequences

- Detectors for tool authorization are simple and reliable.
- Tool implementations must be side-effect-free outside `World` and `Sandbox`.

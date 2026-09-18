# ADR-0003: Verdicts only from trusted, host-side evidence

- Status: accepted
- Date: 2026-09-14

## Context

An agent's self-report ("I accessed the secret", "I did not send the email") is meaningless for security verification: the subject is adversarial. AgentEscapeBench's host-verified proofs and AISI's separation of model execution from tool execution show the right pattern.

## Decision

- Evidence records carry `source` and `trusted`. Only broker, sandbox-host, sinkhole, and orchestrator sources are trusted; `target_transcript` is always untrusted.
- Detectors receive an `EvidenceView` that yields trusted records only, and every `Finding` must cite at least one trusted evidence id (validated).
- Detectors cannot import target, broker, or sandbox implementations (layer test).
- Attack success is declared as predicates over evidence (tool called, network contacted, canary leaked, world changed), never as "the model agreed".

## Consequences

- Some behaviors are harder to detect (e.g. a model *intending* harm without acting). This is accepted: we verify actions.
- Honeytokens and host sentinels become core infrastructure.

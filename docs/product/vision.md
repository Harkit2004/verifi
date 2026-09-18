# Vision

> **Don't trust benchmark scores. Try to break the model.**
> Run untrusted AI against an untrusted world, without trusting either.

## Problem

Companies are deploying AI agents that read email, write to CRMs, call internal APIs, and execute code.
Today they have no neutral, reproducible way to answer:

> *Given the capabilities we grant this agent, can it be made to violate our security contract?*

Public benchmarks get memorized and optimized against. Guardrail vendors sell defenses, not neutral
verification. Sandbox-escape research answers a narrow question. And too many evaluations still trust
what the model *says* it did.

## What verifi is

An open, reproducible, **adversarial verification layer**:

1. Companies declare **what an agent may do** (tools, data, network, filesystem) and **which guarantees must hold** (controls) in a `VerificationSpec`.
2. verifi **actively tries to violate those guarantees** with attack packs (public, private, and generated) delivered through realistic channels: user messages, emails, documents, web pages, database rows, tool outputs.
3. An **independently trusted environment decides** whether the agent actually crossed a boundary, using host-side evidence (tool broker audit, network sinkhole, filesystem diffs, honeytokens), never the agent's self-report.
4. Results are **scored, gated, and tamper-evident**, so they drop into CI/CD like Snyk or Semgrep: "deployment blocked: 1 critical finding (data exfiltration)".

### Honest security claim

We do **not** claim "the model cannot escape". We claim: *even if the evaluated agent escapes its inner
environment, it cannot escape the evaluation boundary, and the escape is detected.* This is why isolation
is tiered and nested (container, then hardened VM) and why verification happens outside the boundary.

## Landscape and positioning

| Category | Examples | Relation to verifi |
|---|---|---|
| General model evaluation | UK AISI **Inspect AI** (datasets, solvers, scorers, sandboxing, 200+ evals) | Interoperate, don't compete: adapter for Inspect tasks and log export (ADR-0006) |
| LLM red teaming | NVIDIA **garak** (jailbreaks, injection, leakage probes) | garak asks "can I make the model fail?"; verifi asks "can the agent violate *this environment's contract* with *real capabilities*?" |
| Sandbox escape research | **SandboxEscapeBench** (AISI, sandbox-in-VM), **AgentEscapeBench** (host-verified escape proofs) | Adopt their principles: nested isolation and host-side proofs |
| Agent security benchmarks | **OASB**, **AgentShield Benchmark** | Standardized controls; verifi makes controls *company-defined* and *continuously attacked* |
| Commercial agent security | Lakera, Protect AI, HiddenLayer, Lasso, ... | Defensive products; verifi is a neutral verification layer that can also test them |

**Differentiator:** company-specific contracts + private tests + adaptive adversarial generation + hardened nested sandbox + independent host-side verification + CI/CD regression tracking, in one open-source tool.

## Product shape

- **Open source `verifi`:** CLI plus library; runs locally and in CI; everything reproducible from spec + seed.
- **Later, a hosted platform:** register agents and models, private benchmarks, history and regression tracking, compliance reports. The platform is a projection of the same operations the CLI exposes (ADR-0002).

## Key concepts

- **Public + private + generated tests:** a model can't simply memorize the benchmark. Previous failures become regression cases.
- **Evaluation Integrity:** meta-evaluation of whether the agent detects the benchmark, infers tests, manipulates the scorer, tampers with evaluation state, or signals outside the evaluation (Phase 3).
- **Adaptive attacker:** from fixed attacks to search (mutate, evaluate, keep what works) to learned attackers; successful exploits are added to the regression suite (Phase 3).

## Phases

| Phase | Outcome |
|---|---|
| 0 Foundation | Package, CLI envelope, operation registry, run store primitives, verification gate |
| 1 Core verification loop | Spec, fake and hardened Docker sandbox, world and honeytokens, tool broker, scripted target, host-side detectors, scoring, gate, tamper-evident reports, `verifi run` |
| 2 Adversarial engine | Attack packs and vehicles, mutators, private packs, real model and container-agent targets, Inspect interop |
| 3 Adaptive attacker | Search-based generation, exploit regression store, evaluation-integrity probes |
| 4 Platform | HTTP API generated from the registry, run index and history, UI with CLI parity |

## Non-goals (for now)

- Capability benchmarking (reasoning, coding quality). Use Inspect.
- Runtime protection or guardrails in production.
- Training models (RL is used for *attackers*, not targets).
- Claims of formal proof of containment.

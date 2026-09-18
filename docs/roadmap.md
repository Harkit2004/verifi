# Roadmap

GitHub Issues are the source of truth; this page is the map. Execution order is decided by
`python scripts/agent/agentctl.py next` from each issue's metadata block (`phase`, then `seq`, gated by `depends-on`).

Legend: **R** = `agent:ready` · **T** = `needs:triage` (planner/triager refine first) · **H** = spike, `needs:human` · ⚠ = `risk:high` (human reviews the PR)

## Phase 0: Foundation. Milestone "Phase 0: Foundation", epic #1

| # | Key | Task | Deps | |
|---|---|---|---|---|
| #12 | P0-01 | scaffold uv package, tooling config, version | | R |
| #13 | P0-02 | errors hierarchy + L0 utils | #12 | R |
| #14 | P0-03 | AppContext, Envelope, operation registry, invoke() | #13 | R |
| #15 | P0-04 | Typer CLI from registry, `--json`, exit codes | #14 | R |
| #16 | P0-05 | envelope JSON Schema + AST layer test | #15 | R |
| #17 | P0-06 | hash-chained EventLog | #13 | R ⚠ |

## Phase 1: Core verification loop. Milestone "Phase 1", epics #2–#8

| # | Key | Task | Epic | |
|---|---|---|---|---|
| #18 | P1-01 | EvidenceRecord trust rules | #3 | R ⚠ |
| #19 | P1-02 | control catalog + `controls.list` | #2 | R |
| #20 | P1-03 | VerificationSpec models | #2 | R |
| #21 | P1-04 | loader, env refs, `spec.validate`, example specs | #2 | R |
| #22 | P1-05 | JSON Schema + `spec.schema` | #2 | R |
| #23 | P1-06 | spec lock + `spec.lock` | #2 | R ⚠ |
| #24 | P1-07 | RunStore + `runs.list/show` | #3 | R |
| #25 | P1-08 | EvidenceStore + trusted EvidenceView | #3 | R ⚠ |
| #26 | P1-09 | BudgetMeter | #3 | R |
| #27 | P1-10 | sandbox protocols + FakeSandbox + contract suite | #4 | R ⚠ |
| #28 | P1-11 | honeytokens + CanaryRegistry | #5 | R ⚠ |
| #29 | P1-12 | world fixtures + crm-support + diff | #5 | R |
| #30 | P1-13 | ToolBroker audit-before-invoke | #5 | R ⚠ |
| #31 | P1-14 | tools fs / email / crm | #5 | R |
| #32 | P1-15 | tools http.request / python.execute + `tools.list` | #5 | R ⚠ |
| #33 | P1-16 | ScriptedTarget + factory | #6 | R |
| #34 | P1-17 | detector engine | #7 | R ⚠ |
| #35 | P1-18 | canary detector | #7 | R ⚠ |
| #36 | P1-19 | tool_auth detector | #7 | R ⚠ |
| #37 | P1-20 | world_integrity detector | #7 | R ⚠ |
| #38 | P1-21 | escape detector | #7 | R ⚠ |
| #39 | P1-22 | score_run | #8 | R ⚠ |
| #40 | P1-23 | evaluate_gate | #8 | R ⚠ |
| #41 | P1-24 | Orchestrator over FakeSandbox | #8 | R ⚠ |
| #42 | P1-25 | reports + verification.json | #3 | R ⚠ |
| #43 | P1-26 | `runs.start` / `verifi run` | #8 | R |
| #44 | P1-27 | `runs.verify`, `findings.list`, `evidence.show`, `reports.render` | #3 | R |
| #45 | P1-28 | `runs.compare` | #3 | R |
| #46 | P1-29 | known-bad/benign agent suite + determinism | #7 | R ⚠ |
| #47 | P1-30 | Docker Tier-1 hardened provider | #4 | R ⚠ |
| #48 | P1-31 | sandbox-base image + `sandbox.doctor` | #4 | R ⚠ |
| #49 | P1-32 | sinkhole network + image | #4 | R ⚠ |
| #50 | P1-33 | escape sentinels on Docker | #4 | R ⚠ |

**Milestone exit:** `verifi run examples/specs/minimal.yaml` passes; malicious scripted agents fail the gate with the expected findings; `verifi runs verify` detects tampering; Docker hardening verified in CI.

## Phase 2: Adversarial engine. Milestone "Phase 2", epic #9 (plus #4, #6)

| # | Key | Task | |
|---|---|---|---|
| #51 | P2-01 | attack models, pack loader, `attacks.list/show` | R |
| #52 | P2-02 | SuccessPredicate evaluator | R ⚠ |
| #53 | P2-03 | vehicles | R |
| #54 | P2-04 | scenario builder + orchestrator integration | R ⚠ |
| #55 | P2-05 | injection detector | R ⚠ |
| #56–#59 | P2-06..09 | builtin packs: prompt-injection, indirect-injection, credentials-exfiltration, tool-abuse-privesc | R |
| #60 | P2-10 | mutators | R |
| #61 | P2-11 | private packs + redaction | R ⚠ |
| #62 | P2-12 | multi-turn attacks | R |
| #63 | P2-13 | OpenAI-compatible target | R |
| #64 | P2-14 | MCP broker exposure | R ⚠ |
| #65 | P2-15 | container-agent target | R ⚠ |
| #66 | P2-16 | composite GitHub Action for CI users | R |
| #67 | P2-17 | Spike: Inspect AI interop | H |
| #68 | P2-18 | Spike: Tier-2 VM isolation | H |

## Phase 3: Adaptive attacker. Milestone "Phase 3", epic #10

| # | Key | Task | |
|---|---|---|---|
| #69 | P3-01 | exploit regression store | T |
| #70 | P3-02 | Spike: search strategy | H |
| #71 | P3-03 | adaptive search loop MVP | T |
| #72 | P3-04 | evaluation-integrity probe pack (needs new control in spec-v1.md) | T |

## Phase 4: Platform. Milestone "Phase 4", epic #11

| # | Key | Task | |
|---|---|---|---|
| #73 | P4-01 | FastAPI from registry + HTTP parity | T |
| #74 | P4-02 | SQLite run index | T |
| #75 | P4-03 | Spike: web UI | H |

## Human decision queue (unblocks later phases)

1. #68 Tier-2 isolation technology (needed before claims about hostile models)
2. #67 Inspect AI interop direction
3. #70 adaptive search strategy
4. #72 requires adding control `no_evaluation_tampering` to `docs/architecture/spec-v1.md`
5. #75 UI scope

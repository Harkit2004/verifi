# Threat model

## Assets

1. **Host and runner infrastructure** (the machine running verifi, the CI runner, cloud credentials).
2. **Evaluation integrity**: findings, scores, and gate decisions reflect what actually happened.
3. **Private attack packs and company-private tests.**
4. **Other runs** on the same host (isolation between runs).
5. **Secrets used by verifi** (model API keys for targets).

## Adversaries

| Adversary | Assumed capability |
|---|---|
| **Target agent / model** (primary) | Fully malicious and capable: will try to escape, exfiltrate, lie in its transcript, detect the benchmark, and tamper with evaluation state reachable from inside. |
| Attack pack author | Semi-trusted: payloads are data, never executed on the host; pack parsing must be safe (YAML safe load, size limits). |
| Spec author | Trusted to define policy, but mistakes happen: unsafe relaxations must be explicit and visible. |
| Network observer | Can observe CI logs and shared reports: no secrets or private payloads in outputs. |

## Trust boundaries

```
B1  target  ->  tool broker          (all tool effects mediated and audited)
B2  sandbox ->  host                 (container / VM isolation; host-side capture)
B3  run     ->  results              (hash-chained artifacts; verification id)
B4  private packs -> reports/logs    (redaction)
B5  host env/secrets -> sandbox      (allowlist only)
```

## Invariants

| Id | Invariant | Enforced by (tests) |
|---|---|---|
| INV-1 | Verdicts come only from trusted evidence; transcripts are untrusted and never reach detectors. | `EvidenceRecord` validator; `EvidenceView`; `run_detectors` check; `tests/contracts/test_untrusted_evidence.py` |
| INV-2 | Sandboxes are default-deny; relaxations are explicit and reported as `SECURITY_RELAXED`. | provider defaults; `inspect()`-based integration tests; spec validation |
| INV-3 | No host secrets, env, Docker socket, or home mounts inside sandboxes. | `SandboxRequest.env` allowlist; docker integration test inspecting `Config.Env` and `Mounts` |
| INV-4 | The broker is the only tool path; audit happens before execution, including denials. | broker unit tests (audit-before-invoke ordering); targets receive only `ToolClient` |
| INV-5 | Run artifacts are tamper-evident. | `EventLog.verify`; `verify_run_dir`; tamper tests that flip one byte |
| INV-6 | Private attack payloads never appear in reports, logs, events, or findings. | redaction unit tests grep all run files for the payload |
| INV-7 | Deterministic runs with fakes and a fixed seed. | `tests/e2e/test_determinism.py` |
| INV-8 | Honeytokens are unique per run and CSPRNG-generated. | honeytoken tests (uniqueness across 1,000 generations; no fixed values in fixtures) |
| INV-9 | Detectors cannot import target, broker, or sandbox implementations. | `tests/contracts/test_layers.py` |
| INV-10 | Sandboxes never outlive their run. | orchestrator `finally` teardown test with a failing target; docker cleanup sweep test |

## Known limitations (documented, accepted for Phases 1-2)

- Tier 1 (Docker) shares the host kernel; a kernel exploit breaks B2. Mitigation: Tier 2 (VM) for hostile models; escape sentinels still detect common escapes.
- TLS egress under `sinkhole` is recorded by SNI and connection only; payloads inside TLS are not inspected. Honeytoken leaks inside TLS may be missed; tools and HTTP vehicles use plain HTTP in the mock world.
- Tamper evidence is not signing.
- For `openai-compatible` targets the model provider sees world content, including honeytokens. Honeytokens are fake, but private attack payloads are sent to the provider by necessity. Users must choose a trusted endpoint for private packs (warning `PRIVATE_PACK_REMOTE_TARGET`).

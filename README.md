# verifi

**Adversarial AI verification.** Run untrusted AI against an untrusted world, without trusting either.

verifi places an AI model or agent inside a strongly isolated, instrumented environment, gives it real
capabilities, attacks it (prompt injection, indirect injection, credential discovery, tool abuse,
sandbox escape, ...), and decides from **host-side evidence**, never from the model's own claims,
whether it violated the security contract you defined.

```yaml
# spec.yaml
apiVersion: verifi.dev/v1
kind: VerificationSpec
metadata: { name: support-agent }
target: { type: openai-compatible, model: my-model, endpoint: "${env:TARGET_ENDPOINT}" }
environment: { isolation: docker, network: none }
tools: [ { name: email.read }, { name: crm.read }, { name: crm.write, constraints: { tables: [tickets] } } ]
policy: { controls: [no_secret_access, no_data_exfiltration, no_unauthorized_tool_use, no_sandbox_escape] }
attacks: { packs: [builtin:prompt-injection, builtin:indirect-injection], seed: 1234 }
gate: { min_overall: 0.95, max_findings: { critical: 0 } }
```

```bash
verifi run spec.yaml            # exit 0 = gate passed, 1 = gate failed
verifi runs verify <run-id>     # re-check the tamper-evident run record
```

> **Status:** pre-alpha. The architecture is designed; implementation is carried out issue by issue by an
> autonomous agent. See [`docs/roadmap.md`](docs/roadmap.md).

## Documentation

- [Vision](docs/product/vision.md) · [Architecture overview](docs/architecture/overview.md) · [Roadmap](docs/roadmap.md)
- Contributors, human or agent: [`AGENTS.md`](AGENTS.md) and [`docs/process/`](docs/process/)

## License

Apache-2.0

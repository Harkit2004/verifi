# CLI contract

The CLI is the primary interface **and** the verification surface for autonomous agents. Everything a UI
or HTTP API does must be doable, and checkable, with `verifi ... --json`.

## Invocation

```
verifi [GLOBAL OPTIONS] <group> <verb> [ARGS] [OPTIONS]
verifi run SPEC            # alias of: verifi runs start SPEC
```

Global options (before the group): `--json`, `--home PATH` (overrides `VERIFI_HOME`, default `~/.verifi`), `--log-level [debug|info|warning|error]` (default warning), `--no-color`.

CLI flags are derived from the operation's input model: field `spec_path: Path` becomes positional `SPEC_PATH` if marked `json_schema_extra={"cli": "argument"}`, otherwise `--spec-path`. Booleans become `--flag/--no-flag`.

## JSON envelope (`schemas/envelope.v1.json`)

In `--json` mode stdout contains **exactly one** JSON document and nothing else; logs go to stderr.

```json
{
  "schema": "verifi.envelope/v1",
  "ok": false,
  "command": "spec.validate",
  "data": null,
  "errors": [
    { "code": "UNKNOWN_CONTROL", "message": "Unknown control 'no_magic'", "path": "/policy/controls/2", "hint": "Run: verifi controls list", "details": {} }
  ],
  "warnings": [],
  "meta": { "verifi_version": "0.1.0", "duration_ms": 12, "run_id": null }
}
```

- `ok` is true iff no errors. A completed run whose **gate failed** is `ok: true` with `data.gate.passed == false` and exit code 1.
- Without `--json`, the same data is rendered for humans; exit codes are identical.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | success; for runs, gate passed |
| 1 | completed but a verification property failed (gate failed, `runs verify` found tampering) |
| 2 | invalid input: bad args, invalid spec, unknown id, not found |
| 3 | environment problem: Docker unavailable, permission denied, image missing |
| 4 | internal error or budget abort of the whole run |
| 130 | interrupted (Ctrl-C); run marked `cancelled` |

## Operations (v1 catalog)

| Operation | CLI | Input (key fields) | Output `data` (key fields) | Phase |
|---|---|---|---|---|
| `version.show` | `verifi version` | | `version`, `python`, `platform` | 0 |
| `ops.list` | `verifi ops list` | | `operations[]: {name, summary, cli}` | 0 |
| `spec.validate` | `verifi spec validate SPEC_PATH` | `spec_path` | `valid`, `name`, `sha256`, `warnings[]` | 1 |
| `spec.schema` | `verifi spec schema` | `output?` | `schema` (object) or `written` path | 1 |
| `spec.lock` | `verifi spec lock SPEC_PATH` | `spec_path` | `locked` (canonical spec), `sha256` | 1 |
| `controls.list` | `verifi controls list` | | `controls[]: {id, title, default_severity, evidence_kinds}` | 1 |
| `tools.list` | `verifi tools list` | | `tools[]: {name, description, egress, constraints}` | 1 |
| `sandbox.doctor` | `verifi sandbox doctor` | `provider=docker` | `available`, `inspection`, `problems[]` | 1 |
| `runs.start` | `verifi runs start SPEC_PATH` / `verifi run` | `spec_path`, `seed?`, `provider?` | `run_id`, `status`, `score`, `gate`, `findings_count`, `verification_id`, `run_dir` | 1 |
| `runs.list` | `verifi runs list` | `limit=20` | `runs[]: {run_id, status, created_at, spec_name, overall, gate_passed}` | 1 |
| `runs.show` | `verifi runs show RUN_ID` | `run_id` | `manifest`, `score`, `gate` | 1 |
| `runs.verify` | `verifi runs verify RUN_ID` | `run_id` | `intact`, `verification_id`, `problems[]` | 1 |
| `runs.compare` | `verifi runs compare BASE_RUN HEAD_RUN` | `base`, `head` | `overall_delta`, `controls[]: {id, base, head, delta}`, `new_findings[]`, `resolved_findings[]`, `regression` | 1 |
| `findings.list` | `verifi findings list RUN_ID` | `run_id`, `severity?`, `control?` | `findings[]` | 1 |
| `evidence.show` | `verifi evidence show RUN_ID EVIDENCE_ID` | `run_id`, `evidence_id` | `record` | 1 |
| `reports.render` | `verifi reports render RUN_ID` | `run_id`, `format=md` | `content` or `written` | 1 |
| `attacks.list` | `verifi attacks list` | `pack?`, `family?` | `cases[]: {id, family, vehicle, targets, severity}` (private payloads omitted) | 2 |
| `attacks.show` | `verifi attacks show CASE_ID` | `case_id` | `case` (payload redacted if private) | 2 |

New operations must be added to this table (via a docs change) before or together with their issue.

## Testing contract

- `tests/contracts/test_operation_parity.py`: every registry entry has a CLI command, and every CLI command maps to a registry entry. In Phase 4 the same holds for HTTP routes.
- `tests/contracts/test_envelope_schema.py`: every CLI JSON output validates against `schemas/envelope.v1.json`.
- Shared fixture `invoke_json(*args) -> dict` runs the Typer app in-process with `--json --home <tmp>`, asserts stdout parses, and exposes `.exit_code` via `invoke_json.last_exit_code`.

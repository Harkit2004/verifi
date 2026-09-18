---
name: cli-route
description: How to add or change a user-facing verifi capability as a registered operation with a --json CLI route, stable envelope, exit codes, and CLI tests, so agents can verify everything without a UI.
---

# CLI route (operation) procedure

verifi is CLI-first. Every capability a UI or HTTP API might offer exists first as an **operation** in the registry, exposed as `verifi <group> <verb>`. Agents verify features through the CLI's `--json` output. Contract: `docs/architecture/cli-contract.md`.

## Steps

1. **Name it:** `<group>.<verb>`, e.g. `spec.validate`, `runs.show`. The CLI becomes `verifi spec validate`. Check the table in `cli-contract.md`; if the operation is listed there, use that exact name, inputs, and outputs.
2. **Models:** define `XInput` and `XOutput` Pydantic models next to the service code (e.g. `src/verifi/spec/operations.py`). Outputs are plain data: no Rich objects, no paths relative to cwd (absolute or run-relative only).
3. **Service function:** `def spec_validate(ctx: AppContext, inp: SpecValidateInput) -> SpecValidateOutput`. It takes an `AppContext` (clock, ids, paths, stdout-free) and never prints. Raise `VerifiError` subclasses with stable `code`s.
4. **Register:**

```python
@operation(name="spec.validate", summary="Validate a VerificationSpec file", input=SpecValidateInput, output=SpecValidateOutput)
def spec_validate(ctx: AppContext, inp: SpecValidateInput) -> SpecValidateOutput: ...
```

   Import the module in `src/verifi/app/operations.py` so registration happens.
5. **CLI:** the CLI is generated from the registry; you normally write no Typer code. Only add a custom human renderer in `src/verifi/cli/render.py` if the issue asks for human-readable output.
6. **Tests (write first):**
   - service unit test calling the function directly,
   - CLI test using `CliRunner` via the `invoke_json` fixture:

```python
def test_spec_validate_ok(invoke_json, examples_dir):
    env = invoke_json("spec", "validate", str(examples_dir / "minimal.yaml"))
    assert env["ok"] is True
    assert env["command"] == "spec.validate"
    assert env["data"]["valid"] is True
```

   - error-path CLI test asserting `ok: false`, the error `code`, and the process exit code.
7. **Parity:** `tests/contracts/test_operation_parity.py` must still pass. It asserts every registered operation has a CLI route, and later an HTTP route too.

## Rules

- In `--json` mode, stdout contains **only** the envelope JSON. Logs go to stderr.
- Exit codes: 0 ok, 1 verification completed but gate failed, 2 invalid input/spec, 3 environment problem (Docker missing, permission denied), 4 internal error, 130 interrupted.
- Never break an existing operation's output fields. Add fields; don't rename or remove. A breaking change requires escalation.
- A UI or API feature without an operation is a bug: register it.

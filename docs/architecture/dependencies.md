# Dependency allowlist

Agents may add **only** these packages, and only in the phase listed. Anything else requires a human
decision (escalate). Versions are lower bounds; `uv.lock` pins exact versions.

## Runtime (`[project.dependencies]`)

| Package | Min version | Purpose | From phase |
|---|---|---|---|
| `typer` | 0.12 | CLI (brings `click`, `rich`) | 0 |
| `pydantic` | 2.7 | models, validation, JSON Schema | 0 |
| `pyyaml` | 6.0 | spec and pack loading (`yaml.safe_load` only) | 1 |
| `httpx` | 0.27 | model endpoint client (`openai-compatible` target) | 1 |
| `docker` | 7.1 | Docker Engine API for the Tier 1 provider | 1 |
| `mcp` | 1.2 | expose broker tools to container agents | 1 |

## Optional extras

| Extra | Packages | Purpose | From phase |
|---|---|---|---|
| `inspect` | `inspect-ai` | Inspect interop (ADR-0006) | 2, after spike |
| `api` | `fastapi`, `uvicorn` | HTTP API projection | 4 |

## Development (`[dependency-groups] dev`)

| Package | Purpose |
|---|---|
| `pytest` ≥ 8 | tests |
| `ruff` ≥ 0.6 | format + lint |
| `mypy` ≥ 1.11 | strict type checking |
| `types-pyyaml` | stubs |
| `jsonschema` ≥ 4.23 | validating envelopes and reports against committed schemas in tests |

## Forbidden

- Mocking frameworks beyond `unittest.mock` (use project fakes).
- Anything that phones home or collects telemetry.
- Unmaintained packages (no release in 2 years), packages without an OSI license, GPL-family licenses in runtime deps (project is Apache-2.0).
- `requests` (use `httpx`), `attrs`/`dataclasses-json` (use pydantic), `click` directly (use typer).

## Tool configuration (in `pyproject.toml`)

- ruff: `line-length = 120`, `target-version = "py312"`, rules `E,F,W,I,B,UP,SIM,RUF,S` (ignore `S101` in tests).
- mypy: `strict = true`, `files = ["src", "tests"]`, `plugins = ["pydantic.mypy"]`.
- pytest: `testpaths = ["tests"]`, `markers = ["docker: requires a Docker daemon", "slow: > 5s"]`, `addopts = "--strict-markers -ra"`, `xfail_strict = true`.

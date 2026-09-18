# ADR-0001: Python 3.12, uv, Typer, Pydantic v2

- Status: accepted
- Date: 2026-09-14

## Context

The AI evaluation ecosystem (Inspect AI, garak, most model SDKs) is Python. We need strict schemas for specs, reports, and CLI envelopes, JSON Schema export, and a CLI that can be generated from typed models. Autonomous agents need one obvious way to install and run everything on Windows, macOS, and Linux.

## Decision

- Python ≥ 3.12, single package `verifi` in `src/` layout.
- **uv** for Python install, virtualenv, locking, and running (`uv run`).
- **Pydantic v2** for all data contracts; JSON Schemas are generated and committed under `schemas/`.
- **Typer** for the CLI, generated from the operation registry (ADR-0002).
- pytest, ruff, mypy strict.

## Consequences

- Easy interop with Inspect AI and model SDKs.
- Performance-critical parts (sinkhole) are small separate processes, which is acceptable.
- Everything runs as `uv run ...`; the harness scripts (`scripts/`) stay stdlib-only so they work before `uv sync`.

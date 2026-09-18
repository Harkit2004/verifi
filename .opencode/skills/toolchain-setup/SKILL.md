---
name: toolchain-setup
description: Diagnose and fix a missing or broken verifi development toolchain (git, gh, uv, Python 3.12, opencode, docker, uv sync) using scripts/agent/bootstrap.py, and what may never be installed without escalation.
---

# Toolchain setup

## Diagnose

```bash
python scripts/agent/bootstrap.py
```

The JSON output lists each tool with `ok`, `detail`, and `required`.

## Fix

```bash
python scripts/agent/bootstrap.py --install
```

This installs **only**: uv (official installer), Python 3.12 via `uv python install`, opencode via npm, project dependencies via `uv sync`.

| Problem | Action |
|---|---|
| `uv` missing after install | open a new shell or add `~/.local/bin` (Windows: `%USERPROFILE%\.local\bin`) to PATH for the command: `export PATH="$HOME/.local/bin:$PATH"` |
| `uv sync` fails on a package | do not pin or swap packages; check `docs/architecture/dependencies.md`; if the allowlisted version is broken, escalate |
| `gh-auth` not ok | you cannot log in; escalate ("runner gh auth expired") |
| `github-labels` not ok | escalate; labels are maintained by humans via `setup_labels.py --apply` |
| docker not ok | fine for most issues (docker tests skip). If your issue needs Docker, hand off with a note that verification needs a Docker host or CI |
| Python package importable in `uv run` but not in plain `python` | always use `uv run ...` for product code |

## Never

- `pip install` into the global interpreter, `sudo`, or system package managers.
- Add a dependency to `pyproject.toml` that is not allowlisted, even as "temporary".
- Download and execute scripts from URLs other than those in `bootstrap.py`.
- Change global git or gh config, or opencode config outside the repo.

## Windows notes

- Use forward slashes in paths passed to Python scripts.
- If a command works in bash but not in PowerShell (or vice versa), prefer `python ...` or `uv run ...` invocations; they behave the same everywhere.

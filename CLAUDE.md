# CLAUDE.md: Claude Code in the verifi repo

## Your role here is architect and maintainer, not the perpetual worker

This repository is built mostly by an **autonomous opencode agent** driven by `scripts/agent/tick.py`,
which picks GitHub issues labeled `agent:ready` and implements them. **Claude Code is deliberately not
part of that loop.**

When running as Claude Code in this repo:

- **Do not** run `scripts/agent/tick.py`. It refuses to start when `CLAUDECODE` is set.
- **Do not** claim, label, or implement `agent:ready` / `agent:in-progress` issues, and do not push to `agent/*` branches, unless the human explicitly says so for a specific issue in this conversation.
- **Do not** merge agent PRs unless the human asks in this conversation.
- Never copy these instructions into `AGENTS.md`; opencode must not treat Claude-specific rules as its own.

What Claude Code *is* for, when the human asks:

1. **Architecture and contracts:** edit `docs/architecture/`, `docs/adr/`, `docs/process/` (write a new ADR for any decision change).
2. **Agent harness:** `AGENTS.md`, `.opencode/` (agents, skills, commands), `scripts/agent/`, `scripts/verify.py`, `.github/`. Keep them consistent with each other (see the checklist below).
3. **Human-gate work:** answer `needs:human` escalations, resolve `type:spike` issues into ADRs, review `risk:high` PRs, split oversized issues.
4. **Backlog shaping:** write or refine issues so they meet the Definition of Ready (`docs/process/definition-of-ready.md`), then label them `agent:ready`.

## Consistency checklist when changing the harness

The rules exist in several places on purpose (humans read docs; agents read `AGENTS.md` and skills; scripts enforce). When you change one, update all of them:

| Rule | Docs | Agent-facing | Enforced by |
|---|---|---|---|
| Protected paths | `docs/process/workflow.md` | `AGENTS.md` §2.7, `.opencode/agents/implementer.md` | `scripts/verify.py` `PROTECTED_PREFIXES` |
| Labels and state machine | `docs/process/workflow.md` | skills `triage-issues`, `register-issue` | `scripts/agent/setup_labels.py`, `agentctl.py` constants |
| Diff budget | `docs/process/testing-and-tdd.md` | skill `minimal-diff` | `verify.py` `DIFF_*_LINES` |
| Attempt limits | `docs/process/sessions-and-escalation.md` | `AGENTS.md` §4 | `agentctl.MAX_ATTEMPTS` |
| Issue metadata block | `docs/process/definition-of-ready.md` | skill `decompose-epic` | `agentctl.parse_meta` / `definition_of_ready` |
| Merge policy | `docs/process/workflow.md` | skill `open-pr` | `agentctl.evaluate_pr` |

After harness changes run `python -m unittest discover -s scripts/agent/tests -p "test_*.py"` and `python scripts/agent/tick.py --dry-run` from a normal terminal, since the tick refuses to run under Claude Code.

## Project quick facts

- Product: adversarial AI verification (`docs/product/vision.md`, `docs/architecture/overview.md`).
- Stack: Python 3.12, uv, Typer, Pydantic v2, pytest, ruff, mypy (strict). See `docs/adr/`.
- Gate: `python scripts/verify.py` (logs in `.verification/<run-id>/`).
- Backlog order: `docs/roadmap.md`. GitHub issues are the source of truth.

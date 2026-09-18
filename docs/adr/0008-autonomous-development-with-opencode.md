# ADR-0008: GitHub Issues as task queue; opencode as the perpetual engineer

- Status: accepted
- Date: 2026-09-14

## Context

The project is intended to be implemented mostly by an unattended agent running on a schedule, including with weaker or cheaper models. That requires a durable queue, durable memory across sessions, deterministic state transitions, objective verification, and hard limits.

## Decision

- **Queue:** GitHub Issues. Hierarchy: milestone (phase), then epic (`type:epic`, sub-issues), then task. Ordering and dependencies live in a machine-readable `<!-- verifi-agent ... -->` block (phase, seq, depends-on, risk, size). Selection is deterministic code (`agentctl.select_next`), not model judgment.
- **Memory:** issue comments with typed markers (`claim`, `session-start`, `handoff`, `escalation`, `session-end`, `resume`), plus the branch itself.
- **Worker:** **opencode** (`opencode run --agent implementer`), launched by `scripts/agent/tick.py` from any scheduler. One session per tick; 3 attempts per issue and 3 fix attempts per PR, then human.
- **Claude Code is excluded** from the loop (tick refuses under `CLAUDECODE`); it serves as architect and maintainer of docs and harness when a human asks.
- **Rules** in `AGENTS.md`; **procedures** as opencode skills; **enforcement** in `scripts/verify.py` (TDD red/green runs, diff budget, protected paths) and CI.
- **Merge policy** is code (`agentctl.evaluate_pr`): green CI + `risk:low` gets an auto squash-merge by the runner; `risk:high` or unknown risk needs `human:approved`.
- **Kill switch:** `.agent/PAUSE`, `VERIFI_AGENT_PAUSED=1`, or any open issue labeled `agent:pause`.

## Consequences

- Humans spend time on specs, escalations, and high-risk reviews rather than implementation.
- Issue quality is the bottleneck, hence the strict Definition of Ready.
- The harness itself is protected and only changes through human (or Claude Code, when asked) PRs.

# Sessions, handoffs, and escalation

## Principles

- **Sessions are disposable; GitHub is memory.** Anything not pushed or written in an issue comment is lost.
- **One session per tick, one issue per session.**
- **Deterministic code decides *what* to work on; the model decides *how*.**

## Runner decision order (each tick)

1. **Paused?** (`.agent/PAUSE`, `VERIFI_AGENT_PAUSED=1`, open issue labeled `agent:pause`): do nothing.
2. **Preflight:** tools present, clean tree, `main` fast-forwarded.
3. **Housekeeping:** evaluate each agent PR, then merge, flag for a human, or escalate; close epics whose sub-issues are all closed.
4. **Resume PR:** first PR needing a fix gets `implementer` on its branch, reusing the last session id if known.
5. **Resume issue:** `agent:in-progress` without an open PR gets a new session (or continues the previous one if its handoff was `partial`).
6. **Work:** `agentctl next`, claim, then `implementer`.
7. **Triage:** up to 10 `needs:triage` issues go to `triager`.
8. **Plan:** open epics go to `planner`, at most once per 24h.
9. Otherwise idle.

## When a session starts new vs continues

| Situation | Session |
|---|---|
| First session on an issue | new |
| Previous handoff `partial` | continue (`opencode run --session <id>`) |
| Previous handoff `blocked`, previous escalation answered, or session ended without handoff | new, with the last handoff or session-end comment in the prompt |
| Fixing own PR | continue the PR's last session if known, else new |
| Triage / plan | always new |

## Limits

| Limit | Value | Where |
|---|---|---|
| Sessions per issue before auto-escalation | 3 | `agentctl.MAX_ATTEMPTS` |
| Fix attempts per PR before auto-escalation | 3 | same |
| Session wall time | 90 min (`VERIFI_AGENT_TIMEOUT`) | `tick.py` |
| Implementer steps | 250 | `.opencode/agents/implementer.md` |
| Planner tasks per session | 8 | skill `decompose-epic` |
| Plan frequency | 24h | `tick.py` |

## Comment markers (machine-readable)

| Marker | Posted by | Attributes |
|---|---|---|
| `<!-- verifi-agent:claim -->` | agentctl claim | `at` |
| `<!-- verifi-agent:session-start -->` | runner | `attempt` |
| `<!-- verifi-agent:handoff -->` | agent via agentctl | `status` (partial/blocked/done), `session` |
| `<!-- verifi-agent:escalation -->` | agent or runner | `session` |
| `<!-- verifi-agent:session-end -->` | runner | `session`, `exit`, `outcome` (pr=N / escalated / no-pr) |
| `<!-- verifi-agent:resume -->` | runner, on PRs | `attempt`, `sha`, `session`, `exit` |
| `<!-- verifi-agent:registered -->` | agentctl register | `issue` |
| `<!-- verifi-agent:discovered -->` | agentctl register (issue body) | `kind`, `found_while` |

## Escalation triggers (agents)

Ambiguous or contradictory requirements; architecture or security decisions; protected paths; new dependencies; secrets, paid APIs, or network in tests; the same failure after 3 different fixes; scope beyond size m; a dependency that did not deliver what the issue assumes.

## Answering an escalation (humans)

1. Reply on the issue with the decision. If it changes contracts, update docs or an ADR first (a Claude Code session can do this).
2. Edit the issue body if acceptance criteria change.
3. Remove `needs:human` and `agent:blocked`; add `agent:ready`.
